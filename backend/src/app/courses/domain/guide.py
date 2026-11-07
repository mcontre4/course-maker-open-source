"""Persistent conversational state, independent of an agent framework."""

from dataclasses import dataclass, replace

from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.standalone import LessonOwnerId
from app.shared.domain.prefixed_uuid import PrefixedUuid


class GuideThreadId(PrefixedUuid):
    prefix = "chat_"


class GuideMessageId(PrefixedUuid):
    prefix = "message_"


class GuideMemoryId(PrefixedUuid):
    prefix = "memory_"


@dataclass(frozen=True)
class GuideThread:
    id: GuideThreadId
    owner_id: str
    resource_id: str
    guide: str
    title: str
    revision: int = 0
    history_json: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        LessonOwnerId(self.owner_id)
        if self.guide not in ("lesson", "syllabus", "storyboard", "animation"):
            raise CourseError("Unknown guide")
        if not self.title.strip() or len(self.title) > 120 or self.revision < 0:
            raise CourseError("Invalid chat")

    def require_revision(self, revision: int) -> None:
        if self.revision != revision:
            raise CourseConflict("Chat changed; reload before sending your message")

    def advance(self, history_json: str, summary: str, message: str = "") -> "GuideThread":
        title = self.title
        if self.revision == 0 and title == "New chat" and message.strip():
            title = " ".join(message.split())[:80]
        return replace(
            self,
            title=title,
            revision=self.revision + 1,
            history_json=history_json,
            summary=summary,
        )


@dataclass(frozen=True)
class GuideTurn:
    id: GuideMessageId
    thread_id: GuideThreadId
    revision: int
    request_id: str
    user: str
    assistant: str
    tool_history_json: str = "[]"

    def __post_init__(self) -> None:
        if not self.user.strip() or len(self.user) > 20000 or not self.assistant.strip():
            raise CourseError("Invalid guide message")
        if self.revision < 1 or not 1 <= len(self.request_id) <= 80:
            raise CourseError("Invalid message identity")


@dataclass(frozen=True)
class GuideMemory:
    id: GuideMemoryId
    owner_id: str
    resource_id: str
    key: str
    content: str
    source_message_id: str
    revision: int = 1

    def __post_init__(self) -> None:
        LessonOwnerId(self.owner_id)
        if not self.key.strip() or len(self.key) > 100:
            raise CourseError("Memory needs a short key")
        if not self.content.strip() or len(self.content) > 2000 or self.revision < 1:
            raise CourseError("Invalid memory")

    def correct(self, content: str, source_message_id: str) -> "GuideMemory":
        return replace(
            self, content=content, source_message_id=source_message_id, revision=self.revision + 1
        )


@dataclass(frozen=True)
class OutlineVersion:
    """A document revision, addressed by resource and revision number."""

    resource_id: str
    revision: int
    outline_json: str
    description: str
    source_message_id: str = ""
    created_at: str = ""
    parent_revision: int | None = None
