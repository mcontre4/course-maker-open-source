import math
from contextlib import nullcontext
from dataclasses import dataclass, replace

from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.lesson_speech import generate_lesson_speech, has_current_speech
from app.courses.application.thumbnail_merge import without_course_images
from app.courses.domain.errors import CourseConflict
from app.courses.domain.identifiers import CourseId
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.speech import SpeechArtifacts, SpeechSynthesizer
from app.courses.ports.spend import UsageTracking
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GenerateSpeechRequest:
    course_id: str
    lesson_id: str


class GenerateSpeech:
    def __init__(
        self,
        courses: CourseRepository,
        synthesizer: SpeechSynthesizer,
        artifacts: SpeechArtifacts,
        settings: SpeechSettings,
        uow: UnitOfWork,
        silence_between_scenes_sec: float = 0.0,
        tracking: UsageTracking | None = None,
    ) -> None:
        if (
            not math.isfinite(silence_between_scenes_sec)
            or not 0 <= silence_between_scenes_sec <= 5
        ):
            raise ValueError("Scene gaps must be between zero and five seconds")
        self._tracking = tracking
        self._courses, self._synthesizer, self._artifacts = courses, synthesizer, artifacts
        self._settings, self._uow, self._gap = settings, uow, silence_between_scenes_sec

    def execute(self, request: GenerateSpeechRequest) -> CourseResponse:
        course_id = CourseId(request.course_id)
        with self._uow:
            before = self._courses.require_by_id(course_id)
            lesson = before.lesson(request.lesson_id)
            if before.status != "ready" or lesson.storyboard is None:
                raise CourseConflict("An approved syllabus and saved storyboard are required")
            style = lesson.style or before.style
            settings = (
                replace(
                    self._settings,
                    voice_id=style.voice_id or self._settings.voice_id,
                    delivery=style.speech_delivery(),
                )
                if style
                else self._settings
            )
            if lesson.alignment is not None:
                if (
                    lesson.alignment.settings != settings
                    or lesson.alignment.silence_between_scenes_sec != self._gap
                ):
                    raise CourseConflict("Audio already exists with different speech settings")
            if not has_current_speech(lesson) and request.lesson_id in before.reviewed:
                raise CourseConflict("Reviewed lessons cannot receive new narration")
        with (
            self._tracking.scope(str(course_id), request.lesson_id, "speech")
            if self._tracking
            else nullcontext()
        ):
            alignment = generate_lesson_speech(
                lesson,
                self._synthesizer,
                self._artifacts,
                settings,
                self._gap,
                f"courses/{course_id}/lessons/{request.lesson_id}/speech",
            )
        if alignment == lesson.alignment:
            return course_response(before)
        with self._uow:
            current = self._courses.require_for_syllabus_change(course_id)
            if without_course_images(current) != without_course_images(before):
                raise CourseConflict("Course changed during speech generation; reload and retry")
            updated = current.align_lesson(request.lesson_id, alignment)
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)
