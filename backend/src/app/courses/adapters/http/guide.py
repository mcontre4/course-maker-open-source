from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.standalone import get_owner
from app.courses.application.guide_chats import (
    ChangeGuideMemory,
    CreateGuideThread,
    GetGuideThread,
    ListGuideMemories,
    ListGuideThreads,
    ListOutlineVersions,
)
from app.courses.application.guide_dto import (
    ChangeGuideMemoryRequest,
    CreateGuideThreadRequest,
    GuideScopeRequest,
    GuideThreadRequest,
    OutlineVersionsRequest,
    SendGuideMessageRequest,
)
from app.courses.application.send_guide_message import SendGuideMessage
from app.courses.domain.generation import GenerationMode


class CreateChatInput(HttpModel):
    resource_id: str = Field(min_length=1, max_length=43)
    guide: Literal["lesson", "syllabus", "storyboard", "animation"] = "lesson"
    title: str = Field(default="New chat", min_length=1, max_length=120)


class SendMessageInput(HttpModel):
    message: str = Field(min_length=1, max_length=20000)
    request_id: str = Field(min_length=1, max_length=80)
    expected_revision: int = Field(ge=0)
    generation_mode: GenerationMode = GenerationMode.BALANCED


class MemoryInput(HttpModel):
    resource_id: str = Field(min_length=1, max_length=43)
    expected_revision: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=2000)


def get_create_chat() -> CreateGuideThread:
    raise NotImplementedError


def get_list_chats() -> ListGuideThreads:
    raise NotImplementedError


def get_chat() -> GetGuideThread:
    raise NotImplementedError


def get_send_message() -> SendGuideMessage:
    raise NotImplementedError


def get_memories() -> ListGuideMemories:
    raise NotImplementedError


def get_change_memory() -> ChangeGuideMemory:
    raise NotImplementedError


def get_versions() -> ListOutlineVersions:
    raise NotImplementedError


router = APIRouter(prefix="/api/v1/guides", tags=["guides"])
Owner = Annotated[str, Depends(get_owner)]


@router.post("/chats", status_code=201)
def create_chat(
    body: CreateChatInput,
    owner: Owner,
    use_case: Annotated[CreateGuideThread, Depends(get_create_chat)],
) -> dict[str, object]:
    return asdict(
        use_case.execute(CreateGuideThreadRequest(owner, body.resource_id, body.guide, body.title))
    )


@router.get("/chats")
def list_chats(
    resource_id: str,
    owner: Owner,
    use_case: Annotated[ListGuideThreads, Depends(get_list_chats)],
    guide: Literal["lesson", "syllabus", "storyboard", "animation"] = "lesson",
) -> dict[str, object]:
    return asdict(use_case.execute(GuideScopeRequest(owner, resource_id, guide)))


@router.get("/chats/{thread_id}")
def read_chat(
    thread_id: str,
    owner: Owner,
    use_case: Annotated[GetGuideThread, Depends(get_chat)],
    before: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    return asdict(use_case.execute(GuideThreadRequest(owner, thread_id, before)))


@router.post("/chats/{thread_id}/messages")
def send_message(
    thread_id: str,
    body: SendMessageInput,
    owner: Owner,
    use_case: Annotated[SendGuideMessage, Depends(get_send_message)],
) -> dict[str, object]:
    return asdict(
        use_case.execute(
            SendGuideMessageRequest(
                owner,
                thread_id,
                body.message,
                body.request_id,
                body.expected_revision,
                body.generation_mode,
            )
        )
    )


@router.get("/memories")
def read_memories(
    resource_id: str, owner: Owner, use_case: Annotated[ListGuideMemories, Depends(get_memories)]
) -> dict[str, object]:
    return asdict(use_case.execute(GuideScopeRequest(owner, resource_id)))


@router.put("/memories/{memory_id}")
def update_memory(
    memory_id: str,
    body: MemoryInput,
    owner: Owner,
    use_case: Annotated[ChangeGuideMemory, Depends(get_change_memory)],
) -> dict[str, object]:
    return asdict(
        use_case.execute(
            ChangeGuideMemoryRequest(
                owner, body.resource_id, memory_id, body.expected_revision, body.content
            )
        )
    )


@router.delete("/memories/{memory_id}")
def forget_saved_memory(
    memory_id: str,
    resource_id: str,
    expected_revision: int,
    owner: Owner,
    use_case: Annotated[ChangeGuideMemory, Depends(get_change_memory)],
) -> dict[str, object]:
    return asdict(
        use_case.execute(
            ChangeGuideMemoryRequest(owner, resource_id, memory_id, expected_revision, delete=True)
        )
    )


@router.get("/outline-versions")
def read_versions(
    resource_id: str,
    owner: Owner,
    use_case: Annotated[ListOutlineVersions, Depends(get_versions)],
    before: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    return asdict(use_case.execute(OutlineVersionsRequest(owner, resource_id, before)))
