"""Server-owned profiles with stateless routing and allowlisted model overrides."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from app.courses.domain.animation import AnimationProject
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animator import AnimationInput, Animator
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.lesson_agent import LessonAgent, LessonAgentRequest, LessonAgentResponse
from app.courses.ports.lesson_quiz import QuizAgent, QuizAgentRequest, QuizAgentResponse
from app.courses.ports.storyboard_agent import (
    StoryboardAgent,
    StoryboardAgentRequest,
    StoryboardAgentResponse,
)
from app.courses.ports.syllabus_agent import (
    SyllabusAgent,
    SyllabusAgentRequest,
    SyllabusAgentResponse,
)


@dataclass(frozen=True)
class GenerationProfile:
    model: str
    reasoning_effort: Literal["medium", "max"]


def generation_profile(
    mode: GenerationMode, model_override: AnimatorModel | None = None
) -> GenerationProfile:
    model = model_override or {
        GenerationMode.FAST: AnimatorModel.SONNET,
        GenerationMode.BALANCED: AnimatorModel.OPUS,
        GenerationMode.PRO: AnimatorModel.OPUS,
    }[mode]
    return GenerationProfile(model.value, "max" if mode is GenerationMode.PRO else "medium")


@dataclass(frozen=True)
class RoutedSyllabusAgent:
    agents: Mapping[GenerationMode, SyllabusAgent]

    def run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse:
        return self.agents[request.generation_mode].run(request)


@dataclass(frozen=True)
class RoutedLessonAgent:
    agents: Mapping[GenerationMode, LessonAgent]

    def run(self, request: LessonAgentRequest) -> LessonAgentResponse:
        return self.agents[request.generation_mode].run(request)


@dataclass(frozen=True)
class RoutedStoryboardAgent:
    agents: Mapping[GenerationMode, StoryboardAgent]

    def run(self, request: StoryboardAgentRequest) -> StoryboardAgentResponse:
        return self.agents[request.generation_mode].run(request)


@dataclass(frozen=True)
class RoutedQuizAgent:
    agents: Mapping[GenerationMode, QuizAgent]

    def run(self, request: QuizAgentRequest) -> QuizAgentResponse:
        return self.agents[request.generation_mode].run(request)


@dataclass(frozen=True)
class RoutedAnimator:
    animators: Mapping[GenerationMode, Animator]
    model_animators: Mapping[tuple[GenerationMode, AnimatorModel], Animator] = field(
        default_factory=dict
    )

    def generate(self, request: AnimationInput) -> AnimationProject:
        if request.animator_model is not None:
            return self.model_animators[request.generation_mode, request.animator_model].generate(
                request
            )
        return self.animators[request.generation_mode].generate(request)

    def verify(self, project: AnimationProject) -> None:
        # Verification only reads an artifact; every profile uses the same artifact root.
        self.animators[GenerationMode.BALANCED].verify(project)
