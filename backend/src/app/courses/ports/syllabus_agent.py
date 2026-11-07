from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.curriculum import Curriculum
from app.courses.domain.duration import Duration
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import CourseId
from app.courses.ports.agent_sessions import AgentSessionContext


@dataclass(frozen=True)
class ConversationTurn:
    user: str
    assistant: str


@dataclass(frozen=True)
class SyllabusConversation:
    course_id: str
    revision: int = 0
    history_json: str = "[]"
    curriculum: Curriculum | None = None
    turns: tuple[ConversationTurn, ...] = ()
    agent_session_id: str | None = None


@dataclass(frozen=True)
class SyllabusLessonContext:
    id: str
    title: str
    topics: tuple[str, ...]
    minutes: int


@dataclass(frozen=True)
class SyllabusChapterContext:
    id: str
    title: str
    summary: str
    lessons: tuple[SyllabusLessonContext, ...]


@dataclass(frozen=True)
class SyllabusCourseContext:
    title: str
    description: str
    duration: Duration
    chapters: tuple[SyllabusChapterContext, ...]


@dataclass(frozen=True)
class SyllabusAgentRequest:
    message: str
    history_json: str
    course: SyllabusCourseContext
    curriculum: Curriculum | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session: AgentSessionContext | None = None


@dataclass(frozen=True)
class SyllabusAgentResponse:
    message: str
    curriculum: Curriculum | None
    history_json: str
    session_id: str | None = None


class SyllabusAgent(Protocol):
    def run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse: ...


class SyllabusConversations(Protocol):
    def get_by_course_id(self, course_id: CourseId) -> SyllabusConversation | None: ...

    def save(self, conversation: SyllabusConversation, expected_revision: int) -> None: ...
