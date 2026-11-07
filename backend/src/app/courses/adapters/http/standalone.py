from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.courses.adapters.http.internal_access import require_internal_access
from app.courses.adapters.http.schema import HttpModel, LessonView, StyleInputView
from app.courses.adapters.http.spend import CourseSpendView
from app.courses.application.copy_lesson import CopyLesson, CopyLessonRequest
from app.courses.application.save_standalone_script import (
    SaveStandaloneScript,
    SaveStandaloneScriptRequest,
)
from app.courses.application.standalone import (
    ApproveStandaloneLesson,
    CreateStandaloneLesson,
    GetStandaloneLesson,
    ListStandaloneLessons,
    PlanStandaloneLesson,
    UpdateStandaloneLesson,
)
from app.courses.application.standalone_dto import (
    CreateStandaloneLessonRequest,
    ListStandaloneLessonsRequest,
    ReviseStandaloneLessonRequest,
    StandaloneLessonRequest,
    UpdateStandaloneLessonRequest,
)
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.application.standalone_spend import GetStandaloneSpend, RefreshStandaloneSpend
from app.courses.domain.generation import GenerationMode
from app.courses.domain.standalone import LessonFlow
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator_model import AnimatorModel


class CopyLessonInput(HttpModel):
    course_id: str | None = None
    title: Annotated[str, Field(min_length=1, max_length=120)] | None = None


def get_copy() -> CopyLesson:
    raise RuntimeError("Lesson copying is not configured")


class CreateLessonInput(HttpModel):
    flow: LessonFlow = LessonFlow.GUIDED
    title: Annotated[str, Field(max_length=120)] = ""
    description: Annotated[str, Field(max_length=2000)] = ""
    minutes: Annotated[int, Field(ge=1, le=10, strict=True)]
    style: StyleInputView
    generation_mode: GenerationMode = GenerationMode.BALANCED


class RevisionInput(HttpModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    script_session_id: str | None = Field(default=None, min_length=1, max_length=100)
    reviewer_session_id: str | None = Field(default=None, min_length=1, max_length=100)
    job_id: str | None = Field(default=None, min_length=1, max_length=100)
    message: str = Field(default="", max_length=2000)
    regenerate_from: Literal["script", "speech", "animation"] | None = None
    generation_mode: GenerationMode = Field(default=GenerationMode.BALANCED, alias="generationMode")
    expected_revision: Annotated[int, Field(ge=0, strict=True)]


class AnimationRevisionInput(RevisionInput):
    prepare_elements: bool = Field(default=False, strict=True)
    animator_model: AnimatorModel | None = None
    animation_backend: AnimationBackend = AnimationBackend.DIRECT


class PlanLessonInput(RevisionInput):
    message: Annotated[str, Field(min_length=1, max_length=2000)]


class UpdateLessonInput(CreateLessonInput):
    expected_revision: Annotated[int, Field(ge=0, strict=True)]


class LessonTurnView(HttpModel):
    user: str
    assistant: str


class StandaloneLessonView(HttpModel):
    flow: LessonFlow
    id: str
    owner_id: str
    description: str
    revision: int
    approved: bool
    content: LessonView
    turns: tuple[LessonTurnView, ...]
    playback_content: LessonView | None = None


class ScriptInput(RevisionInput):
    narrations: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=16000)]],
        Field(min_length=1, max_length=100),
    ]


def get_save_script() -> SaveStandaloneScript:
    raise RuntimeError("Script editing is not configured")


class StandaloneLessonListView(HttpModel):
    items: tuple[StandaloneLessonView, ...]


def get_owner() -> str:
    raise RuntimeError("Lesson owner identity is not configured")


def get_create() -> CreateStandaloneLesson:
    raise RuntimeError("Standalone lessons are not configured")


def get_update() -> UpdateStandaloneLesson:
    raise RuntimeError("Standalone lessons are not configured")


def get_list() -> ListStandaloneLessons:
    raise RuntimeError("Standalone lessons are not configured")


def get_lesson() -> GetStandaloneLesson:
    raise RuntimeError("Standalone lessons are not configured")


def get_plan() -> PlanStandaloneLesson:
    raise RuntimeError("Lesson agent is not configured")


def get_approve() -> ApproveStandaloneLesson:
    raise RuntimeError("Standalone lessons are not configured")


def get_storyboard() -> GenerateStandaloneStoryboard:
    raise RuntimeError("Storyboard agent is not configured")


def get_speech() -> GenerateStandaloneSpeech:
    raise RuntimeError("Speech generation is not configured")


def get_animation() -> GenerateStandaloneAnimation:
    raise RuntimeError("Animation generation is not configured")


router = APIRouter(prefix="/api/v1/lessons", tags=["standalone lessons"])
Owner = Annotated[str, Depends(get_owner)]


@router.put("/{lesson_id}/script", response_model=StandaloneLessonView)
def save_script(
    lesson_id: str,
    payload: ScriptInput,
    owner: Owner,
    service: Annotated[SaveStandaloneScript, Depends(get_save_script)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            SaveStandaloneScriptRequest(
                lesson_id, owner, payload.expected_revision, tuple(payload.narrations)
            )
        )
    )


@router.post("/{lesson_id}/copy", response_model=StandaloneLessonView, status_code=201)
def copy_lesson(
    lesson_id: str,
    payload: CopyLessonInput,
    owner: Owner,
    service: Annotated[CopyLesson, Depends(get_copy)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(CopyLessonRequest(lesson_id, owner, payload.course_id, payload.title))
    )


@router.post("", response_model=StandaloneLessonView, status_code=201)
def create_lesson(
    payload: CreateLessonInput,
    owner: Owner,
    service: Annotated[CreateStandaloneLesson, Depends(get_create)],
) -> StandaloneLessonView:
    result = service.execute(
        CreateStandaloneLessonRequest(
            owner,
            payload.title,
            payload.description,
            payload.minutes,
            payload.style.to_request() if payload.style else None,
            payload.generation_mode,
            flow=payload.flow,
        )
    )
    return StandaloneLessonView.model_validate(result)


@router.get("", response_model=StandaloneLessonListView)
def list_lessons(
    owner: Owner,
    service: Annotated[ListStandaloneLessons, Depends(get_list)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StandaloneLessonListView:
    return StandaloneLessonListView.model_validate(
        service.execute(ListStandaloneLessonsRequest(owner, limit, offset))
    )


@router.get("/{lesson_id}", response_model=StandaloneLessonView)
def get_lesson_by_id(
    lesson_id: str, owner: Owner, service: Annotated[GetStandaloneLesson, Depends(get_lesson)]
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(StandaloneLessonRequest(lesson_id, owner))
    )


@router.put("/{lesson_id}", response_model=StandaloneLessonView)
def update_lesson(
    lesson_id: str,
    payload: UpdateLessonInput,
    owner: Owner,
    service: Annotated[UpdateStandaloneLesson, Depends(get_update)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            UpdateStandaloneLessonRequest(
                lesson_id,
                owner,
                payload.expected_revision,
                payload.title,
                payload.description,
                payload.minutes,
                payload.style.to_request() if payload.style else None,
                flow=payload.flow if "flow" in payload.model_fields_set else None,
            )
        )
    )


@router.post("/{lesson_id}/plan", response_model=StandaloneLessonView)
def plan_lesson(
    lesson_id: str,
    payload: PlanLessonInput,
    owner: Owner,
    service: Annotated[PlanStandaloneLesson, Depends(get_plan)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                payload.expected_revision,
                payload.message,
                generation_mode=payload.generation_mode,
                regenerate_from=payload.regenerate_from,
                session_id=payload.session_id,
                script_session_id=payload.script_session_id,
                reviewer_session_id=payload.reviewer_session_id,
                job_id=payload.job_id,
            )
        )
    )


@router.post("/{lesson_id}/approve", response_model=StandaloneLessonView)
def approve_lesson(
    lesson_id: str,
    payload: RevisionInput,
    owner: Owner,
    service: Annotated[ApproveStandaloneLesson, Depends(get_approve)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                payload.expected_revision,
                generation_mode=payload.generation_mode,
                regenerate_from=payload.regenerate_from,
                session_id=payload.session_id,
                script_session_id=payload.script_session_id,
                reviewer_session_id=payload.reviewer_session_id,
                job_id=payload.job_id,
            )
        )
    )


@router.post("/{lesson_id}/storyboard", response_model=StandaloneLessonView)
def storyboard_lesson(
    lesson_id: str,
    payload: RevisionInput,
    owner: Owner,
    service: Annotated[GenerateStandaloneStoryboard, Depends(get_storyboard)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                payload.expected_revision,
                generation_mode=payload.generation_mode,
                message=payload.message,
                regenerate_from=payload.regenerate_from,
                session_id=payload.session_id,
                script_session_id=payload.script_session_id,
                reviewer_session_id=payload.reviewer_session_id,
                job_id=payload.job_id,
            )
        )
    )


@router.post("/{lesson_id}/speech", response_model=StandaloneLessonView)
def speak_lesson(
    lesson_id: str,
    payload: RevisionInput,
    owner: Owner,
    service: Annotated[GenerateStandaloneSpeech, Depends(get_speech)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                payload.expected_revision,
                generation_mode=payload.generation_mode,
                regenerate_from=payload.regenerate_from,
                session_id=payload.session_id,
                script_session_id=payload.script_session_id,
                reviewer_session_id=payload.reviewer_session_id,
                job_id=payload.job_id,
            )
        )
    )


@router.post("/{lesson_id}/animation", response_model=StandaloneLessonView)
def animate_lesson(
    lesson_id: str,
    payload: AnimationRevisionInput,
    owner: Owner,
    service: Annotated[GenerateStandaloneAnimation, Depends(get_animation)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                payload.expected_revision,
                generation_mode=payload.generation_mode,
                animator_model=payload.animator_model,
                prepare_elements=payload.prepare_elements,
                animation_backend=payload.animation_backend,
                message=payload.message,
                regenerate_from=payload.regenerate_from,
                session_id=payload.session_id,
                script_session_id=payload.script_session_id,
                reviewer_session_id=payload.reviewer_session_id,
                job_id=payload.job_id,
            )
        )
    )


def get_spend_reader() -> GetStandaloneSpend:
    raise RuntimeError("Standalone spend reader is not configured")


def get_spend_refresher() -> RefreshStandaloneSpend:
    raise RuntimeError("Standalone spend refresher is not configured")


@router.get(
    "/{lesson_id}/spend",
    response_model=CourseSpendView,
    dependencies=[Depends(require_internal_access)],
)
def read_lesson_spend(
    lesson_id: str, owner: Owner, service: Annotated[GetStandaloneSpend, Depends(get_spend_reader)]
) -> CourseSpendView:
    return CourseSpendView.model_validate(
        service.execute(StandaloneLessonRequest(lesson_id, owner))
    )


@router.post(
    "/{lesson_id}/spend/refresh",
    response_model=CourseSpendView,
    dependencies=[Depends(require_internal_access)],
)
def refresh_lesson_spend(
    lesson_id: str,
    owner: Owner,
    service: Annotated[RefreshStandaloneSpend, Depends(get_spend_refresher)],
) -> CourseSpendView:
    return CourseSpendView.model_validate(
        service.execute(StandaloneLessonRequest(lesson_id, owner))
    )
