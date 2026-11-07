from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.domain.lesson_quiz import LessonQuiz, LessonQuizAttempt, LessonQuizQuestion
from app.courses.domain.storyboard import Storyboard
from app.courses.ports.agent_sessions import AgentSessionContext


class QuizGenerationUnavailable(Exception):
    pass


class LessonQuizzes(Protocol):
    def get_by_lesson_id(self, lesson_id: LessonId) -> LessonQuiz | None: ...

    def save(self, quiz: LessonQuiz) -> None: ...

    def add_attempt(self, attempt: LessonQuizAttempt) -> None: ...

    def list_attempts(
        self, lesson_id: LessonId, learner_id: str, limit: int, offset: int
    ) -> tuple[LessonQuizAttempt, ...]: ...


@dataclass(frozen=True)
class QuizAgentRequest:
    plan: LessonPlan
    storyboard: Storyboard | None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session: AgentSessionContext | None = None


@dataclass(frozen=True)
class QuizAgentResponse:
    questions: tuple[LessonQuizQuestion, ...]
    session_id: str | None = None


class QuizAgent(Protocol):
    def run(self, request: QuizAgentRequest) -> QuizAgentResponse: ...


@dataclass(frozen=True)
class QuizJob:
    lesson_id: str
    owner_id: str
    generation_mode: GenerationMode = GenerationMode.BALANCED


class QuizJobs(Protocol):
    def enqueue(self, job: QuizJob) -> None: ...
