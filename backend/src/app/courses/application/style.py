from dataclasses import asdict, replace

from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.standalone_dto import StandaloneLessonResponse, standalone_response
from app.courses.application.style_dto import (
    ListVoicesRequest,
    ListVoicesResponse,
    UpdateStyleRequest,
    VoiceResponse,
)
from app.courses.application.style_resolution import resolve_style
from app.courses.application.thumbnail_merge import (
    with_course_images,
    without_course_images,
    without_lesson_image,
)
from app.courses.domain.errors import CourseConflict
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.spend import UsageTracking
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.courses.ports.style import StylePlanner, VoiceCatalog
from app.shared.application.unit_of_work import UnitOfWork


class ListVoices:
    def __init__(self, catalog: VoiceCatalog) -> None:
        self._catalog = catalog

    def execute(self, request: ListVoicesRequest) -> ListVoicesResponse:
        term = request.search.casefold()
        return ListVoicesResponse(
            tuple(
                VoiceResponse(**asdict(v))
                for v in self._catalog.list()
                if term in (v.name + " " + v.description + " " + " ".join(v.labels)).casefold()
            )
        )


class UpdateStandaloneStyle:
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        planner: StylePlanner | None = None,
        voices: VoiceCatalog | None = None,
        tracking: UsageTracking | None = None,
    ) -> None:
        self._lessons, self._uow = lessons, uow
        self._planner, self._voices, self._tracking = planner, voices, tracking

    def execute(self, request: UpdateStyleRequest) -> StandaloneLessonResponse:
        identifier = LessonId(request.resource_id)
        with self._uow:
            before = self._lessons.require_by_id(identifier)
            before.require_owner(request.owner_id)
            previous = before.content.style
            if request.expected_version != (previous.version if previous else 0):
                raise CourseConflict("Style changed; reload before saving")
        style = resolve_style(
            before.description,
            request.style,
            request.generation_mode,
            self._planner,
            self._voices,
            previous,
            self._tracking,
            lesson_id=str(identifier),
        )
        content = before.content.restyle(style)
        updated = replace(
            before,
            content=content,
            revision=before.revision + 1,
            approved=before.approved and content.plan is not None,
        )
        with self._uow:
            current = self._lessons.require_for_change(identifier)
            current.require_owner(request.owner_id)
            if without_lesson_image(current) != without_lesson_image(before):
                raise CourseConflict("Lesson changed while planning style; reload and retry")
            updated = replace(
                updated, content=replace(updated.content, image=current.content.image)
            )
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)


class UpdateCourseStyle:
    def __init__(
        self,
        courses: CourseRepository,
        uow: UnitOfWork,
        planner: StylePlanner | None = None,
        voices: VoiceCatalog | None = None,
        tracking: UsageTracking | None = None,
    ) -> None:
        self._courses, self._uow = courses, uow
        self._planner, self._voices, self._tracking = planner, voices, tracking

    def execute(self, request: UpdateStyleRequest) -> CourseResponse:
        identifier = CourseId(request.resource_id)
        with self._uow:
            before = self._courses.require_by_id(identifier)
            lesson = before.lesson(request.lesson_id) if request.lesson_id else None
            previous = lesson.style if lesson else before.style
            if request.expected_version != (previous.version if previous else 0):
                raise CourseConflict("Style changed; reload before saving")
            before.require_style_change(request.lesson_id)
        style = (
            None
            if lesson and request.style is None
            else resolve_style(
                before.description,
                request.style,
                request.generation_mode,
                self._planner,
                self._voices,
                previous or before.style,
                self._tracking,
                course_id=str(identifier),
                lesson_id=request.lesson_id,
            )
        )
        if style is not None:
            # An inherited profile can be reused for a voice-only override, but
            # the override owns its version independently from the course.
            style = replace(style, version=previous.version + 1 if previous else 1)
        updated = before.restyle(style, request.lesson_id)
        with self._uow:
            current = self._courses.require_for_syllabus_change(identifier)
            if without_course_images(current) != without_course_images(before):
                raise CourseConflict("Course changed while planning style; reload and retry")
            updated = with_course_images(updated, current)
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)
