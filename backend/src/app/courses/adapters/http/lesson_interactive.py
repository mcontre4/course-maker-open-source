from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import ConfigDict, Field

from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.lesson_interactive import InteractiveServices
from app.courses.application.lesson_interactive_dto import (
    ChangeInteractiveRequest,
    CreateInteractiveRequest,
    InteractiveRequest,
    LessonInteractivesRequest,
    PublicInteractivesRequest,
    PublishInteractiveRequest,
    ReorderInteractivesRequest,
    RestoreInteractiveRequest,
    SaveInteractiveDetailsRequest,
)
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_interactive import BuildStage

router = APIRouter(prefix="/api/v1/lessons/{lesson_id}/interactives", tags=["lesson interactives"])
public_router = APIRouter(prefix="/api/v1/published/lessons", tags=["learner interactives"])


class InteractiveVersionView(HttpModel):
    session_id: str | None = None
    number: int
    request: str
    created_at: str


class InteractiveBuildView(HttpModel):
    request: str
    started_at: str
    stage: BuildStage


class InteractiveFailureView(HttpModel):
    request: str
    message: str


class LearnerInteractiveView(HttpModel):
    model_config = ConfigDict(str_strip_whitespace=False)
    id: str
    lesson_id: str
    version: int
    title: str
    goal: str
    prompts: tuple[str, ...]
    html: str


class InteractiveView(HttpModel):
    model_config = ConfigDict(str_strip_whitespace=False)
    id: str
    lesson_id: str
    brief: str
    title: str
    goal: str
    prompts: tuple[str, ...]
    revision: int
    created_at: str
    updated_at: str
    versions: tuple[InteractiveVersionView, ...]
    current_version: int | None
    html: str | None
    published_version: int | None
    published_html: str | None
    build: InteractiveBuildView | None
    failure: InteractiveFailureView | None


class InteractivesView(HttpModel):
    items: tuple[InteractiveView, ...]


class PublicInteractivesView(HttpModel):
    items: tuple[LearnerInteractiveView, ...]


class CreateInteractiveInput(HttpModel):
    brief: Annotated[str, Field(min_length=1, max_length=2000)]
    generation_mode: GenerationMode = GenerationMode.BALANCED


class RevisionInput(HttpModel):
    expected_revision: Annotated[int, Field(ge=1, strict=True)]


class ChangeInteractiveInput(RevisionInput):
    instruction: Annotated[str, Field(min_length=1, max_length=1000)]


class InteractiveDetailsInput(RevisionInput):
    title: Annotated[str, Field(min_length=1, max_length=80)]
    goal: Annotated[str, Field(max_length=200)]
    prompts: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=160)], ...], Field(max_length=6)
    ]


class PublishInteractiveInput(HttpModel):
    version: Annotated[int, Field(ge=1, strict=True)] | None


class ReorderInteractivesInput(HttpModel):
    ids: Annotated[tuple[str, ...], Field(max_length=10)]


def get_interactives() -> InteractiveServices:
    raise RuntimeError("Lesson interactives are not configured")


Services = Annotated[InteractiveServices, Depends(get_interactives)]


@router.get("")
def list_interactives(lesson_id: str, owner: Owner, services: Services) -> InteractivesView:
    return InteractivesView.model_validate(
        services.list.execute(LessonInteractivesRequest(lesson_id, owner))
    )


@router.post("", status_code=201)
def create_interactive(
    lesson_id: str,
    body: CreateInteractiveInput,
    owner: Owner,
    services: Services,
) -> InteractiveView:
    return InteractiveView.model_validate(
        services.create.execute(
            CreateInteractiveRequest(lesson_id, owner, body.brief, body.generation_mode)
        )
    )


@router.put("/order")
def reorder_interactives(
    lesson_id: str,
    body: ReorderInteractivesInput,
    owner: Owner,
    services: Services,
) -> InteractivesView:
    return InteractivesView.model_validate(
        services.reorder.execute(ReorderInteractivesRequest(lesson_id, owner, body.ids))
    )


@router.get("/{id}")
def read_interactive(lesson_id: str, id: str, owner: Owner, services: Services) -> InteractiveView:
    return InteractiveView.model_validate(
        services.get.execute(InteractiveRequest(lesson_id, owner, id))
    )


@router.patch("/{id}")
def save_details(
    lesson_id: str,
    id: str,
    body: InteractiveDetailsInput,
    owner: Owner,
    services: Services,
) -> InteractiveView:
    return InteractiveView.model_validate(
        services.details.execute(
            SaveInteractiveDetailsRequest(
                lesson_id, owner, id, body.title, body.goal, body.prompts, body.expected_revision
            )
        )
    )


@router.delete("/{id}", status_code=204)
def delete_interactive(lesson_id: str, id: str, owner: Owner, services: Services) -> Response:
    services.delete.execute(InteractiveRequest(lesson_id, owner, id))
    return Response(status_code=204)


@router.post("/{id}/changes")
def change_interactive(
    lesson_id: str,
    id: str,
    body: ChangeInteractiveInput,
    owner: Owner,
    services: Services,
) -> InteractiveView:
    return InteractiveView.model_validate(
        services.change.execute(
            ChangeInteractiveRequest(lesson_id, owner, id, body.instruction, body.expected_revision)
        )
    )


@router.post("/{id}/build/retry")
def retry_build(lesson_id: str, id: str, owner: Owner, services: Services) -> InteractiveView:
    return InteractiveView.model_validate(
        services.retry.execute(InteractiveRequest(lesson_id, owner, id))
    )


@router.post("/{id}/build/cancel")
def cancel_build(lesson_id: str, id: str, owner: Owner, services: Services) -> InteractiveView:
    return InteractiveView.model_validate(
        services.cancel.execute(InteractiveRequest(lesson_id, owner, id))
    )


@router.post("/{id}/versions/{number}/restore")
def restore_version(
    lesson_id: str,
    id: str,
    number: Annotated[int, Field(ge=1)],
    body: RevisionInput,
    owner: Owner,
    services: Services,
) -> InteractiveView:
    return InteractiveView.model_validate(
        services.restore.execute(
            RestoreInteractiveRequest(lesson_id, owner, id, number, body.expected_revision)
        )
    )


@router.put("/{id}/published")
def publish_version(
    lesson_id: str,
    id: str,
    body: PublishInteractiveInput,
    owner: Owner,
    services: Services,
) -> InteractiveView:
    return InteractiveView.model_validate(
        services.publish.execute(PublishInteractiveRequest(lesson_id, owner, id, body.version))
    )


@public_router.get("/{lesson_id}/interactives")
def public_interactives(lesson_id: str, services: Services) -> PublicInteractivesView:
    return PublicInteractivesView.model_validate(
        services.public.execute(PublicInteractivesRequest(lesson_id))
    )
