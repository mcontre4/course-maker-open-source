from typing import Annotated

from fastapi import Depends

from app.courses.adapters.http.internal_access import require_internal_access
from app.courses.adapters.http.schema import HttpModel
from app.courses.application.spend import (
    GetCourseSpend,
    RefreshCourseSpend,
    SpendRequest,
)


class SpendTotalView(HttpModel):
    known_usd: str
    pending_calls: int
    estimated_calls: int
    calls: int
    input_tokens: int
    output_tokens: int
    credits: str


class LessonSpendView(HttpModel):
    lesson_id: str
    total: SpendTotalView


class SpendBreakdownView(HttpModel):
    lesson_id: str | None
    stage: str
    provider: str
    model: str
    total: SpendTotalView


class GenerationStepView(HttpModel):
    id: str
    lesson_id: str | None
    stage: str
    started_at: float
    finished_at: float | None
    backend: str | None = None


class CourseSpendView(HttpModel):
    currency: str
    total: SpendTotalView
    shared: SpendTotalView
    lessons: tuple[LessonSpendView, ...]
    breakdown: tuple[SpendBreakdownView, ...]
    steps: tuple[GenerationStepView, ...] = ()


def get_spend_reader() -> GetCourseSpend:
    raise RuntimeError("Spend reader is not configured")


def get_spend_refresher() -> RefreshCourseSpend:
    raise RuntimeError("Spend refresher is not configured")


def read_spend(
    course_id: str,
    service: Annotated[GetCourseSpend, Depends(get_spend_reader)],
    access: Annotated[None, Depends(require_internal_access)],
) -> CourseSpendView:
    return CourseSpendView.model_validate(service.execute(SpendRequest(course_id)))


def refresh_spend(
    course_id: str,
    service: Annotated[RefreshCourseSpend, Depends(get_spend_refresher)],
    access: Annotated[None, Depends(require_internal_access)],
) -> CourseSpendView:
    return CourseSpendView.model_validate(service.execute(SpendRequest(course_id)))
