from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.curriculum import Curriculum
from app.courses.domain.generation import GenerationMode
from app.courses.domain.guide import (
    GuideMemory,
    GuideThread,
    GuideThreadId,
    GuideTurn,
    OutlineVersion,
)
from app.courses.domain.lesson_plan import LessonPlan


class GuideRepository(Protocol):
    def add(self, thread: GuideThread) -> None: ...
    def require_by_id(self, thread_id: GuideThreadId) -> GuideThread: ...
    def list_threads(
        self, owner_id: str, resource_id: str, guide: str
    ) -> tuple[GuideThread, ...]: ...
    def save(self, thread: GuideThread, expected_revision: int) -> None: ...
    def add_turn(self, turn: GuideTurn) -> None: ...
    def list_turns(
        self, thread_id: GuideThreadId, before: int | None = None, limit: int = 100
    ) -> tuple[GuideTurn, ...]: ...
    def get_by_request_id(self, thread_id: GuideThreadId, request_id: str) -> GuideTurn | None: ...
    def list_memories(self, owner_id: str, resource_id: str) -> tuple[GuideMemory, ...]: ...
    def save_memory(self, memory: GuideMemory, expected_revision: int) -> None: ...
    def delete_memory(self, owner_id: str, memory_id: str, expected_revision: int) -> None: ...
    def list_versions(
        self, resource_id: str, limit: int = 50, before: int | None = None
    ) -> tuple[OutlineVersion, ...]: ...
    def require_version(self, resource_id: str, revision: int) -> OutlineVersion: ...
    def add_version(self, version: OutlineVersion) -> None: ...
    def annotate_version(
        self, resource_id: str, revision: int, description: str, source_message_id: str
    ) -> None: ...
    def search_history(
        self, owner_id: str, resource_id: str, query: str
    ) -> tuple[GuideTurn, ...]: ...


@dataclass(frozen=True)
class GuideToolRequest:
    operation: str
    revision: int = 0
    other_revision: int = 0
    text: str = ""
    key: str = ""
    scope: str = "lesson"


@dataclass(frozen=True)
class GuideToolResponse:
    content: str


@dataclass(frozen=True)
class GuideAgentRequest:
    message: str
    context_json: str
    history_json: str
    summary: str
    generation_mode: GenerationMode = GenerationMode.BALANCED


@dataclass(frozen=True)
class GuideAgentResponse:
    message: str
    history_json: str
    summary: str
    tool_history_json: str = "[]"


class GuideAgent(Protocol):
    def run(
        self, request: GuideAgentRequest, tool: Callable[[GuideToolRequest], GuideToolResponse]
    ) -> GuideAgentResponse: ...


class GuideOutlineCodec(Protocol):
    def decode_plan(self, value: str) -> LessonPlan: ...
    def decode_curriculum(self, value: str) -> Curriculum: ...
