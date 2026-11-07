from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_interactive import (
    InteractiveId,
    InteractiveLesson,
    InteractivePage,
    LessonInteractive,
)
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.ports.agent_sessions import AgentSessionContext


class InteractiveGenerationUnavailable(Exception):
    pass


class InteractiveLessons(Protocol):
    def require_by_id(self, lesson_id: LessonId) -> InteractiveLesson: ...
    def require_for_change(self, lesson_id: LessonId) -> InteractiveLesson: ...


class LessonInteractives(Protocol):
    def list_by_lesson_id(self, lesson_id: LessonId) -> tuple[LessonInteractive, ...]: ...
    def get_by_id(self, identifier: InteractiveId) -> LessonInteractive | None: ...
    def add(self, interactive: LessonInteractive, lesson: InteractiveLesson) -> None: ...
    def save(self, interactive: LessonInteractive) -> None: ...
    def delete(self, interactive: LessonInteractive) -> None: ...
    def reorder(self, lesson_id: LessonId, identifiers: tuple[InteractiveId, ...]) -> None: ...


@dataclass(frozen=True)
class InteractiveAgentRequest:
    title: str
    description: str
    topics: tuple[str, ...]
    audience: str
    outline: LessonPlan | None
    brief: str
    instruction: str
    current_html: str | None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session: AgentSessionContext | None = None


class InteractiveAgent(Protocol):
    def run(self, request: InteractiveAgentRequest) -> InteractivePage: ...


@dataclass(frozen=True)
class InteractiveJob:
    lesson_id: str
    interactive_id: str
    token: str


class InteractiveJobs(Protocol):
    def enqueue(self, job: InteractiveJob) -> None: ...
