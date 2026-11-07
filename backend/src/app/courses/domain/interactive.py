"""One optional, versioned learning activity for a lesson."""

import hashlib
import json
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal

from app.courses.domain.errors import CourseError
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.domain.validation import text


@dataclass(frozen=True)
class InteractiveSpec:
    kind: Literal["pendulum", "custom"]
    title: str
    objective: str
    explanation: str
    controls: tuple[str, ...]
    behavior: str
    prompts: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    initial_length: float = 1.0
    initial_gravity: float = 9.81
    initial_angle: float = 15.0

    def __post_init__(self) -> None:
        if self.kind not in ("pendulum", "custom"):
            raise CourseError("Unsupported interactive kind")
        text(self.title, 160)
        for value in (self.objective, self.explanation, self.behavior):
            text(value, 4000)
        for values in (self.controls, self.prompts, self.acceptance_criteria):
            if not 1 <= len(values) <= 6:
                raise CourseError("Interactives need 1–6 controls, prompts and acceptance criteria")
            for value in values:
                text(value, 1000)
        for number, low, high in (
            (self.initial_length, 0.2, 3),
            (self.initial_gravity, 0.1, 25),
            (self.initial_angle, 1, 30),
        ):
            if not isfinite(number) or not low <= number <= high:
                raise CourseError("Interactive defaults are outside the supported range")


@dataclass(frozen=True)
class InteractiveDecision:
    reason: str
    spec: InteractiveSpec | None

    def __post_init__(self) -> None:
        text(self.reason, 2000)


@dataclass(frozen=True)
class LessonInteractive:
    """A skipped decision or exactly one built activity, bound to a lesson plan."""

    plan_hash: str
    reason: str
    spec: InteractiveSpec | None
    document: str | None

    def __post_init__(self) -> None:
        if len(self.plan_hash) != 64 or any(c not in "0123456789abcdef" for c in self.plan_hash):
            raise CourseError("Interactive requires its source plan hash")
        text(self.reason, 2000)
        if (self.spec is None) != (self.document is None):
            raise CourseError("A recommended interactive must have a built document")
        if self.document is not None:
            text(self.document, 150000)

    def validate_plan(self, plan: LessonPlan) -> None:
        if self.plan_hash != lesson_plan_hash(plan):
            raise CourseError("Interactive belongs to an outdated lesson plan")
        if self.spec is not None and self.spec.objective not in plan.objectives:
            raise CourseError("Interactive objective must belong to its lesson plan")


def lesson_plan_hash(plan: LessonPlan) -> str:
    payload = asdict(plan)
    if plan.feasibility_status is None:
        # New assessment defaults must not invalidate activities saved with the old schema.
        for field in (
            "feasibility_status", "feasibility_explanation",
            "recommended_video_minutes", "recommended_scope_adjustment",
        ):
            payload.pop(field)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
