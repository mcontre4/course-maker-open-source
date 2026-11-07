from collections.abc import Callable
from typing import Protocol

from app.courses.domain.animation import AnimationProject
from app.courses.ports.visual_production import VisualReview


class AnimationDelivery(Protocol):
    """Notify source_ready after review/repair selection, before final encoding."""

    def deliver(
        self,
        project: AnimationProject,
        *,
        review: bool,
        repair_feedback: str | None = None,
        source_ready: Callable[[], None] | None = None,
    ) -> VisualReview: ...
