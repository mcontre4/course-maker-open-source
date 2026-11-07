from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.courses.domain.animation import AnimationProject
from app.courses.domain.curriculum import CourseGuide
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.domain.speech import LessonAlignment
from app.courses.domain.storyboard import Storyboard
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animation_elements import PreparedAnimationElement
from app.courses.ports.animator_model import AnimatorModel


class AnimationUnavailable(Exception):
    pass


@dataclass(frozen=True)
class AnimationChangeRequest:
    scene_ids: tuple[str, ...]
    reason: str
    requested_change: str


class StoryboardChangeRequired(Exception):
    def __init__(self, change: AnimationChangeRequest) -> None:
        super().__init__(change.reason)
        self.change = change


@dataclass(frozen=True)
class AnimationInput:
    guide: CourseGuide
    plan: LessonPlan
    storyboard: Storyboard
    alignment: LessonAlignment
    audio: tuple[bytes, ...]
    visual_style: str
    generation_mode: GenerationMode = GenerationMode.BALANCED
    asset_project_key: str = ""
    asset_output_hash: str = ""
    visual_feedback: str = ""
    previous_project_key: str = ""
    animator_model: AnimatorModel | None = None
    visual_style_id: str = "flat-vector-science"
    visual_style_version: int = 1
    review_output: bool = True
    existing_project: AnimationProject | None = None
    animation_backend: AnimationBackend = AnimationBackend.DIRECT
    source_ready: Callable[[AnimationProject], None] | None = field(
        default=None, compare=False, repr=False
    )
    regeneration_key: str = ""
    session: AgentSessionContext | None = None
    reviewer_session_id: str | None = None
    prepare_elements: bool = False
    prepared_elements: tuple[PreparedAnimationElement, ...] = ()


class Animator(Protocol):
    def generate(self, request: AnimationInput) -> AnimationProject: ...

    def verify(self, project: AnimationProject) -> None: ...
