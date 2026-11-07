"""Run the complete saved video pipeline independently of browser navigation."""

from dataclasses import dataclass, field, replace

from app.courses.application.dto import CourseResponse
from app.courses.application.generate_animation import GenerateAnimation, GenerateAnimationRequest
from app.courses.application.generate_lesson import GenerateLesson, GenerateLessonRequest
from app.courses.application.generate_speech import GenerateSpeech, GenerateSpeechRequest
from app.courses.application.generate_storyboard import (
    GenerateStoryboard,
    GenerateStoryboardRequest,
)
from app.courses.application.standalone import ApproveStandaloneLesson
from app.courses.application.standalone_dto import (
    ReviseStandaloneLessonRequest,
    StandaloneLessonResponse,
)
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator_model import AnimatorModel


class GenerateStandaloneScript:
    def __init__(
        self, approval: ApproveStandaloneLesson, storyboard: GenerateStandaloneStoryboard
    ) -> None:
        self._approval, self._storyboard = approval, storyboard

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        current = self._approval.execute(request)
        return self._storyboard.execute(replace(request, expected_revision=current.revision))


class GenerateStandaloneVideo:
    def __init__(
        self,
        approval: ApproveStandaloneLesson,
        storyboard: GenerateStandaloneStoryboard,
        speech: GenerateStandaloneSpeech,
        animation: GenerateStandaloneAnimation,
    ) -> None:
        self._approval, self._storyboard = approval, storyboard
        self._speech, self._animation = speech, animation

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        current = self._approval.execute(request)
        for step in (self._storyboard, self._speech, self._animation):
            current = step.execute(replace(request, expected_revision=current.revision))
        return current


@dataclass(frozen=True)
class GenerateCourseVideoRequest:
    course_id: str
    lesson_id: str
    generation_mode: GenerationMode = GenerationMode.BALANCED
    animator_model: AnimatorModel | None = None
    prepare_elements: bool = field(default=False, kw_only=True)
    animation_backend: AnimationBackend = AnimationBackend.DIRECT


class GenerateCourseVideo:
    def __init__(
        self,
        outline: GenerateLesson,
        storyboard: GenerateStoryboard,
        speech: GenerateSpeech,
        animation: GenerateAnimation,
    ) -> None:
        self._outline, self._storyboard = outline, storyboard
        self._speech, self._animation = speech, animation

    def execute(self, request: GenerateCourseVideoRequest) -> CourseResponse:
        self._outline.execute(
            GenerateLessonRequest(request.course_id, request.lesson_id, request.generation_mode)
        )
        self._storyboard.execute(
            GenerateStoryboardRequest(
                request.course_id, request.lesson_id, generation_mode=request.generation_mode
            )
        )
        self._speech.execute(GenerateSpeechRequest(request.course_id, request.lesson_id))
        return self._animation.execute(
            GenerateAnimationRequest(
                request.course_id,
                request.lesson_id,
                "Follow the saved course and lesson style.",
                request.generation_mode,
                request.animator_model,
                request.animation_backend,
                prepare_elements=request.prepare_elements,
            )
        )
