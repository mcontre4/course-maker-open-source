from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.curriculum import CourseGuide, PlannedChapter, PlannedLesson
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.ports.agent_sessions import AgentSessionContext


class LessonGenerationUnavailable(Exception):
    pass


@dataclass(frozen=True)
class LessonAgentRequest:
    course_title: str
    brief: PlannedLesson
    guide: CourseGuide
    chapter: PlannedChapter
    previous_lesson: PlannedLesson | None
    next_lesson: PlannedLesson | None
    description: str = ""
    previous_plan: LessonPlan | None = None
    conversation: tuple[tuple[str, str], ...] = ()
    message: str = ""
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session: AgentSessionContext | None = None


@dataclass(frozen=True)
class LessonAgentResponse:
    plan: LessonPlan
    model: str
    requests: int
    tool_calls: int
    total_tokens: int
    session_id: str | None = None


class LessonAgent(Protocol):
    def run(self, request: LessonAgentRequest) -> LessonAgentResponse: ...
