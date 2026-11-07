from dataclasses import dataclass

from app.courses.domain.errors import ContentNotReady
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.lesson_video import LessonVideo
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GetStandaloneLessonVideoRequest:
    lesson_id: str
    owner_id: str
    source_hash: str | None = None


@dataclass(frozen=True)
class GetCourseLessonVideoRequest:
    course_id: str
    lesson_id: str
    source_hash: str | None = None


@dataclass(frozen=True)
class LessonVideoResponse:
    content: bytes


class GetStandaloneLessonVideo:
    def __init__(self, lessons: StandaloneLessons, videos: LessonVideo, uow: UnitOfWork) -> None:
        self._lessons, self._videos, self._uow = lessons, videos, uow

    def execute(self, request: GetStandaloneLessonVideoRequest) -> LessonVideoResponse:
        with self._uow:
            lesson = self._lessons.require_by_id(LessonId(request.lesson_id))
            lesson.require_owner(request.owner_id)
            version = lesson.content.playback_version(request.source_hash)
            animation = version.animation if version else None
            if animation is None:
                raise ContentNotReady("Generate the lesson animation before watching its video")
        # Rendering and artifact I/O must never hold a database transaction open.
        return LessonVideoResponse(self._videos.read(animation))


class GetCourseLessonVideo:
    def __init__(self, courses: CourseRepository, videos: LessonVideo, uow: UnitOfWork) -> None:
        self._courses, self._videos, self._uow = courses, videos, uow

    def execute(self, request: GetCourseLessonVideoRequest) -> LessonVideoResponse:
        with self._uow:
            lesson = self._courses.require_by_id(CourseId(request.course_id)).lesson(
                request.lesson_id
            )
            version = lesson.playback_version(request.source_hash)
            animation = version.animation if version else None
            if animation is None:
                raise ContentNotReady("Generate the lesson animation before watching its video")
        return LessonVideoResponse(self._videos.read(animation))
