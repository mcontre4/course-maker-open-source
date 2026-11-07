from contextlib import nullcontext
from dataclasses import dataclass, replace

from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.standalone_dto import StandaloneLessonResponse, standalone_response
from app.courses.domain.errors import CourseConflict
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.style import LessonStyle
from app.courses.domain.visual_style import VisualStyle
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.spend import UsageTracking
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.courses.ports.thumbnails import ThumbnailGenerator, ThumbnailUnavailable
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class ThumbnailRequest:
    resource_id: str
    owner_id: str = ""
    lesson_id: str | None = None
    regenerate: bool = False


def _thumbnail_direction(style: LessonStyle | None) -> str:
    # The selected preset is stable while outline planning resolves narration and pacing.
    preset = (
        VisualStyle(style.visual_style_id, style.visual_style_version) if style else VisualStyle()
    )
    return preset.direction()


def initial_thumbnail(
    generator: ThumbnailGenerator | None,
    tracking: UsageTracking | None,
    title: str,
    description: str,
    topics: tuple[str, ...] = (),
    *,
    style: LessonStyle | None = None,
    course_id: str | None = None,
    lesson_id: str | None = None,
) -> str:
    """Draft saving and lesson planning must survive an unavailable image provider."""
    if generator is None:
        return ""
    try:
        with tracking.scope(course_id, lesson_id, "thumbnail") if tracking else nullcontext():
            return generator.generate(
                title,
                description,
                topics,
                visual_direction=_thumbnail_direction(style),
            )
    except ThumbnailUnavailable:
        return ""


class GenerateStandaloneThumbnail:
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        generator: ThumbnailGenerator,
        tracking: UsageTracking | None = None,
    ) -> None:
        self._lessons, self._uow = lessons, uow
        self._generator, self._tracking = generator, tracking

    def execute(self, request: ThumbnailRequest) -> StandaloneLessonResponse:
        identifier = LessonId(request.resource_id)
        with self._uow:
            before = self._lessons.require_by_id(identifier)
            before.require_owner(request.owner_id)
            if before.content.image and not request.regenerate:
                return standalone_response(before)
        with (
            self._tracking.scope(None, str(identifier), "thumbnail")
            if self._tracking
            else nullcontext()
        ):
            image = self._generator.generate(
                before.content.title,
                before.description,
                before.content.topics,
                visual_direction=_thumbnail_direction(before.content.style),
            )
        with self._uow:
            current = self._lessons.require_for_change(identifier)
            current.require_owner(request.owner_id)
            if (
                current.content.title,
                current.description,
                current.content.topics,
                current.content.image,
                _thumbnail_direction(current.content.style),
            ) != (
                before.content.title,
                before.description,
                before.content.topics,
                before.content.image,
                _thumbnail_direction(before.content.style),
            ):
                raise CourseConflict("Lesson changed during thumbnail generation; reload and retry")
            updated = replace(current, content=replace(current.content, image=image))
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)


class GenerateCourseThumbnail:
    def __init__(
        self,
        courses: CourseRepository,
        uow: UnitOfWork,
        generator: ThumbnailGenerator,
        tracking: UsageTracking | None = None,
    ) -> None:
        self._courses, self._uow = courses, uow
        self._generator, self._tracking = generator, tracking

    def execute(self, request: ThumbnailRequest) -> CourseResponse:
        identifier = CourseId(request.resource_id)
        with self._uow:
            before = self._courses.require_by_id(identifier)
            lesson = before.lesson(request.lesson_id) if request.lesson_id else None
            source = lesson if lesson else before
            if source.image and not request.regenerate:
                return course_response(before)
        style = (lesson.style if lesson else None) or before.style or LessonStyle()
        with (
            self._tracking.scope(str(identifier), request.lesson_id, "thumbnail")
            if self._tracking
            else nullcontext()
        ):
            image = self._generator.generate(
                source.title,
                before.description,
                lesson.topics if lesson else (),
                visual_direction=_thumbnail_direction(style),
            )
        with self._uow:
            current = self._courses.require_for_syllabus_change(identifier)
            current_lesson = current.lesson(request.lesson_id) if request.lesson_id else None
            latest = current_lesson if current_lesson else current
            current_style = (current_lesson.style if current_lesson else None) or current.style
            if _thumbnail_direction(current_style) != _thumbnail_direction(style):
                raise CourseConflict("Style changed during thumbnail generation; reload and retry")
            if (latest.title, current.description, latest.image) != (
                source.title,
                before.description,
                source.image,
            ) or (current_lesson and lesson and current_lesson.topics != lesson.topics):
                raise CourseConflict("Course changed during thumbnail generation; reload and retry")
            updated = (
                current._replace_lesson(replace(current_lesson, image=image))
                if current_lesson
                else replace(current, image=image)
            )
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)
