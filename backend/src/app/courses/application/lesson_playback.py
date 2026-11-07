from dataclasses import dataclass

from app.courses.domain.errors import ContentNotReady
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.lesson_playback import LessonPlayback
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GetStandaloneLessonPlaybackRequest:
    lesson_id: str
    owner_id: str
    preview: bool = False
    source_hash: str | None = None


@dataclass(frozen=True)
class GetCourseLessonPlaybackRequest:
    course_id: str
    lesson_id: str
    preview: bool = False
    source_hash: str | None = None


@dataclass(frozen=True)
class LessonPlaybackResponse:
    source_hash: str
    video_ready: bool = False
    preview_html: str | None = None


class GetStandaloneLessonPlayback:
    def __init__(self, lessons: StandaloneLessons, playback: LessonPlayback, uow: UnitOfWork):
        self._lessons, self._playback, self._uow = lessons, playback, uow

    def execute(self, request: GetStandaloneLessonPlaybackRequest) -> LessonPlaybackResponse:
        with self._uow:
            lesson = self._lessons.require_by_id(LessonId(request.lesson_id))
            lesson.require_owner(request.owner_id)
            version = lesson.content.playback_version(request.source_hash)
            if version is None and request.source_hash is not None:
                raise ContentNotReady("Animation changed; reload playback")
            animation = version.animation if version else None
            if animation is None:
                raise ContentNotReady("Animation code is not ready yet")
            if request.source_hash is not None and request.source_hash != animation.output_hash:
                raise ContentNotReady("Animation changed; reload playback")
        if request.preview:
            return LessonPlaybackResponse(
                animation.output_hash, preview_html=self._playback.preview(animation)
            )
        return LessonPlaybackResponse(animation.output_hash, self._playback.video_ready(animation))


class GetCourseLessonPlayback:
    def __init__(self, courses: CourseRepository, playback: LessonPlayback, uow: UnitOfWork):
        self._courses, self._playback, self._uow = courses, playback, uow

    def execute(self, request: GetCourseLessonPlaybackRequest) -> LessonPlaybackResponse:
        with self._uow:
            lesson = self._courses.require_by_id(CourseId(request.course_id)).lesson(
                request.lesson_id
            )
            version = lesson.playback_version(request.source_hash)
            if version is None and request.source_hash is not None:
                raise ContentNotReady("Animation changed; reload playback")
            animation = version.animation if version else None
            if animation is None:
                raise ContentNotReady("Animation code is not ready yet")
            if request.source_hash is not None and request.source_hash != animation.output_hash:
                raise ContentNotReady("Animation changed; reload playback")
        if request.preview:
            return LessonPlaybackResponse(
                animation.output_hash, preview_html=self._playback.preview(animation)
            )
        return LessonPlaybackResponse(animation.output_hash, self._playback.video_ready(animation))
