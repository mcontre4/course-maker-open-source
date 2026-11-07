from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.animation import AnimationProject
from app.courses.ports.animator import AnimationInput


@dataclass(frozen=True)
class VisualAssets:
    project_key: str
    output_hash: str


@dataclass(frozen=True)
class VisualReview:
    approved: bool
    feedback: str
    repair_target: str = "animation"
    session_id: str | None = None


class VisualAssetGenerator(Protocol):
    def generate(self, request: AnimationInput) -> VisualAssets: ...


class AnimationReviewer(Protocol):
    def review(self, project: AnimationProject) -> VisualReview: ...
