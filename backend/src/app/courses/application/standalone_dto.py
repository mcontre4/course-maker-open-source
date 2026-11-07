from dataclasses import dataclass, field
from typing import Literal

from app.courses.application.dto import LessonResponse, lesson_response
from app.courses.application.style_dto import StyleInput
from app.courses.domain.generation import GenerationMode
from app.courses.domain.standalone import LessonFlow, StandaloneLesson
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator_model import AnimatorModel


@dataclass(frozen=True)
class LessonTurnResponse:
    user: str
    assistant: str


@dataclass(frozen=True)
class StandaloneLessonResponse:
    id: str
    owner_id: str
    description: str
    revision: int
    approved: bool
    content: LessonResponse
    turns: tuple[LessonTurnResponse, ...]
    playback_content: LessonResponse | None = None
    flow: LessonFlow = LessonFlow.GUIDED


@dataclass(frozen=True)
class StandaloneLessonRequest:
    lesson_id: str
    owner_id: str


@dataclass(frozen=True)
class ReviseStandaloneLessonRequest:
    lesson_id: str
    owner_id: str
    expected_revision: int
    message: str = ""
    generation_mode: GenerationMode = GenerationMode.BALANCED
    animator_model: AnimatorModel | None = None
    prepare_elements: bool = field(default=False, kw_only=True)
    animation_backend: AnimationBackend = AnimationBackend.DIRECT
    regenerate_from: Literal["script", "speech", "animation"] | None = None
    session_id: str | None = None
    script_session_id: str | None = None
    reviewer_session_id: str | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class CreateStandaloneLessonRequest:
    owner_id: str
    title: str = ""
    description: str = ""
    minutes: int = 3
    style: StyleInput | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    flow: LessonFlow = LessonFlow.GUIDED


@dataclass(frozen=True)
class UpdateStandaloneLessonRequest:
    lesson_id: str
    owner_id: str
    expected_revision: int
    title: str = ""
    description: str = ""
    minutes: int = 3
    style: StyleInput | None = None
    flow: LessonFlow | None = None


@dataclass(frozen=True)
class ListStandaloneLessonsRequest:
    owner_id: str
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class ListStandaloneLessonsResponse:
    items: tuple[StandaloneLessonResponse, ...]


def standalone_response(lesson: StandaloneLesson) -> StandaloneLessonResponse:
    playback = lesson.content.playback_version()
    return StandaloneLessonResponse(
        str(lesson.content.id),
        str(lesson.owner_id),
        lesson.description,
        lesson.revision,
        lesson.approved,
        lesson_response(lesson.content),
        tuple(LessonTurnResponse(t.user, t.assistant) for t in lesson.turns),
        lesson_response(playback)
        if playback is not None and playback != lesson.content and playback.is_published
        else None,
        flow=lesson.flow,
    )
