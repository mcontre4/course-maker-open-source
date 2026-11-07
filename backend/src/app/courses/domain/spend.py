from dataclasses import dataclass
from decimal import Decimal
from math import isfinite

from app.courses.domain.errors import CourseError


@dataclass(frozen=True)
class ModelCharge:
    id: str
    course_id: str | None
    lesson_id: str | None
    stage: str
    provider: str
    model: str
    provider_request_id: str | None = None
    usd: Decimal | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    credits: Decimal | None = None
    estimated: bool = False

    def __post_init__(self) -> None:
        if self.course_id is None and self.lesson_id is None:
            raise CourseError("A charge must belong to a course or standalone lesson")
        for amount in (self.usd, self.credits):
            if amount is not None and (not amount.is_finite() or amount < 0):
                raise CourseError("Charges must be finite and nonnegative")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise CourseError("Token counts must be nonnegative")
        if self.estimated and self.usd is None:
            raise CourseError("An estimated charge needs a dollar amount")


@dataclass(frozen=True)
class GenerationStep:
    id: str
    course_id: str | None
    lesson_id: str | None
    stage: str
    started_at: float
    finished_at: float | None = None
    backend: str | None = None

    def __post_init__(self) -> None:
        if self.course_id is None and self.lesson_id is None:
            raise CourseError("A step must belong to a course or standalone lesson")
        if (
            not isfinite(self.started_at)
            or self.started_at < 0
            or (
                self.finished_at is not None
                and (not isfinite(self.finished_at) or self.finished_at < self.started_at)
            )
        ):
            raise CourseError("Invalid generation step timestamps")


def generation_seconds(steps: tuple[GenerationStep, ...], now: float) -> float | None:
    """Cumulative recorded processing time, with parallel intervals counted once."""
    if not steps:
        return None
    intervals = sorted(
        (
            step.started_at,
            max(step.started_at, step.finished_at if step.finished_at is not None else now),
        )
        for step in steps
    )
    total = 0.0
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


@dataclass(frozen=True)
class SpendTotal:
    known_usd: Decimal
    pending_calls: int
    estimated_calls: int
    calls: int
    input_tokens: int
    output_tokens: int
    credits: Decimal


def sum_charges(charges: tuple[ModelCharge, ...]) -> SpendTotal:
    return SpendTotal(
        sum((c.usd for c in charges if c.usd is not None), Decimal(0)),
        sum(c.usd is None for c in charges),
        sum(c.estimated for c in charges),
        len(charges),
        sum(c.input_tokens for c in charges),
        sum(c.output_tokens for c in charges),
        sum((c.credits for c in charges if c.credits is not None), Decimal(0)),
    )
