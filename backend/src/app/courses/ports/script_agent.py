from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.curriculum import CourseGuide
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.script import LessonScript
from app.courses.ports.agent_sessions import AgentSessionContext

SCRIPT_PROMPT_VERSION = "1"


@dataclass(frozen=True)
class ScriptAgentRequest:
    plan: LessonPlan
    guide: CourseGuide
    target_video_minutes: int
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session: AgentSessionContext | None = None
    message: str = ""

    def __post_init__(self) -> None:
        self.plan.require_feasible()


@dataclass(frozen=True)
class ScriptAgentResponse:
    script: LessonScript
    usage: PlanGeneration


class ScriptAgent(Protocol):
    def run(self, request: ScriptAgentRequest) -> ScriptAgentResponse: ...
