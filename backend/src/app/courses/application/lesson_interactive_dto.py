from dataclasses import dataclass

from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_interactive import BuildStage, LessonInteractive


@dataclass(frozen=True)
class LessonInteractivesRequest:
    lesson_id: str
    owner_id: str


@dataclass(frozen=True)
class InteractiveRequest(LessonInteractivesRequest):
    id: str


@dataclass(frozen=True)
class CreateInteractiveRequest(LessonInteractivesRequest):
    brief: str
    generation_mode: GenerationMode = GenerationMode.BALANCED


@dataclass(frozen=True)
class ChangeInteractiveRequest(InteractiveRequest):
    instruction: str
    expected_revision: int


@dataclass(frozen=True)
class SaveInteractiveDetailsRequest(InteractiveRequest):
    title: str
    goal: str
    prompts: tuple[str, ...]
    expected_revision: int


@dataclass(frozen=True)
class RestoreInteractiveRequest(InteractiveRequest):
    version: int
    expected_revision: int


@dataclass(frozen=True)
class PublishInteractiveRequest(InteractiveRequest):
    version: int | None


@dataclass(frozen=True)
class ReorderInteractivesRequest(LessonInteractivesRequest):
    ids: tuple[str, ...]


@dataclass(frozen=True)
class PublicInteractivesRequest:
    lesson_id: str


@dataclass(frozen=True)
class BuildInteractiveRequest:
    lesson_id: str
    id: str
    token: str


@dataclass(frozen=True)
class BuildInteractiveResponse:
    completed: bool


@dataclass(frozen=True)
class DeletedInteractiveResponse:
    pass


@dataclass(frozen=True)
class InteractiveVersionResponse:
    number: int
    request: str
    created_at: str
    session_id: str | None = None


@dataclass(frozen=True)
class InteractiveBuildResponse:
    request: str
    started_at: str
    stage: BuildStage


@dataclass(frozen=True)
class InteractiveFailureResponse:
    request: str
    message: str


@dataclass(frozen=True)
class InteractiveResponse:
    id: str
    lesson_id: str
    brief: str
    title: str
    goal: str
    prompts: tuple[str, ...]
    revision: int
    created_at: str
    updated_at: str
    versions: tuple[InteractiveVersionResponse, ...]
    current_version: int | None
    html: str | None
    published_version: int | None
    published_html: str | None
    build: InteractiveBuildResponse | None
    failure: InteractiveFailureResponse | None


@dataclass(frozen=True)
class InteractivesResponse:
    items: tuple[InteractiveResponse, ...]


@dataclass(frozen=True)
class LearnerInteractiveResponse:
    id: str
    lesson_id: str
    version: int
    title: str
    goal: str
    prompts: tuple[str, ...]
    html: str


@dataclass(frozen=True)
class PublicInteractivesResponse:
    items: tuple[LearnerInteractiveResponse, ...]


def interactive_response(item: LessonInteractive) -> InteractiveResponse:
    current = item.version(item.current_version)
    published = item.version(item.published_version)
    return InteractiveResponse(
        str(item.id),
        str(item.lesson_id),
        item.brief,
        item.details.title,
        item.details.goal,
        item.details.prompts,
        item.revision,
        item.created_at,
        item.updated_at,
        tuple(
            InteractiveVersionResponse(v.number, v.request, v.created_at, v.session_id)
            for v in item.versions
        ),
        item.current_version,
        current.html if current else None,
        item.published_version,
        published.html if published else None,
        InteractiveBuildResponse(item.build.request, item.build.started_at, item.build.stage)
        if item.build
        else None,
        InteractiveFailureResponse(item.failure.request, item.failure.message)
        if item.failure
        else None,
    )
