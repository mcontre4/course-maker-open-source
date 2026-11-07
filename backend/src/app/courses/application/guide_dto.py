from dataclasses import dataclass

from app.courses.domain.generation import GenerationMode


@dataclass(frozen=True)
class GuideScopeRequest:
    owner_id: str
    resource_id: str
    guide: str = "lesson"


@dataclass(frozen=True)
class CreateGuideThreadRequest(GuideScopeRequest):
    title: str = "New chat"


@dataclass(frozen=True)
class GuideThreadRequest:
    owner_id: str
    thread_id: str
    before: int | None = None


@dataclass(frozen=True)
class SendGuideMessageRequest:
    owner_id: str
    thread_id: str
    message: str
    request_id: str
    expected_revision: int
    generation_mode: GenerationMode = GenerationMode.BALANCED


@dataclass(frozen=True)
class GuideTurnResponse:
    id: str
    revision: int
    user: str
    assistant: str


@dataclass(frozen=True)
class GuideThreadResponse:
    id: str
    resource_id: str
    guide: str
    title: str
    revision: int
    turns: tuple[GuideTurnResponse, ...] = ()
    has_more: bool = False


@dataclass(frozen=True)
class GuideThreadsResponse:
    items: tuple[GuideThreadResponse, ...]


@dataclass(frozen=True)
class GuideMemoryResponse:
    id: str
    scope: str
    key: str
    content: str
    source_message_id: str
    revision: int


@dataclass(frozen=True)
class GuideMemoriesResponse:
    items: tuple[GuideMemoryResponse, ...]


@dataclass(frozen=True)
class ChangeGuideMemoryRequest:
    owner_id: str
    resource_id: str
    memory_id: str
    expected_revision: int
    content: str = ""
    delete: bool = False


@dataclass(frozen=True)
class OutlineVersionsRequest:
    owner_id: str
    resource_id: str
    before: int | None = None


@dataclass(frozen=True)
class OutlineVersionResponse:
    revision: int
    outline_json: str
    description: str
    source_message_id: str
    created_at: str
    parent_revision: int | None = None


@dataclass(frozen=True)
class OutlineVersionsResponse:
    items: tuple[OutlineVersionResponse, ...]
