from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.curriculum import CourseGuide
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.script import LessonScript
from app.courses.domain.storyboard import Storyboard
from app.courses.domain.visual_style import VisualStyle
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.script_agent import SCRIPT_PROMPT_VERSION

STORYBOARD_PROMPT_VERSION = f"script-{SCRIPT_PROMPT_VERSION}/storyboard-9"


class StoryboardGenerationUnavailable(Exception):
    pass


@dataclass(frozen=True)
class StoryboardAgentRequest:
    plan: LessonPlan
    guide: CourseGuide
    target_video_minutes: int
    visual_style: str | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    visual_style_id: str = "flat-vector-science"
    visual_style_version: int = 1
    session: AgentSessionContext | None = None
    script_session_id: str | None = None
    message: str = ""

    def __post_init__(self) -> None:
        self.plan.require_feasible()
        VisualStyle(self.visual_style_id, self.visual_style_version)


@dataclass(frozen=True)
class StoryboardAgentResponse:
    storyboard: Storyboard
    usage: PlanGeneration
    script_session_id: str | None = None


@dataclass(frozen=True)
class VisualStoryboardRequest:
    script: LessonScript
    guide: CourseGuide
    visual_style: str | None = None
    visual_style_id: str = "flat-vector-science"
    visual_style_version: int = 1
    session: AgentSessionContext | None = None
    message: str = ""

    def __post_init__(self) -> None:
        VisualStyle(self.visual_style_id, self.visual_style_version)


class VisualStoryboardAgent(Protocol):
    def run(self, request: VisualStoryboardRequest) -> StoryboardAgentResponse: ...


class StoryboardAgent(Protocol):
    def run(self, request: StoryboardAgentRequest) -> StoryboardAgentResponse: ...
