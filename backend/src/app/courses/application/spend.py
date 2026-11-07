from dataclasses import dataclass

from app.courses.domain.identifiers import CourseId
from app.courses.domain.spend import GenerationStep, ModelCharge, sum_charges
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.spend import Billing, SpendRepository
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class SpendRequest:
    course_id: str


@dataclass(frozen=True)
class SpendTotalResponse:
    known_usd: str
    pending_calls: int
    estimated_calls: int
    calls: int
    input_tokens: int
    output_tokens: int
    credits: str


@dataclass(frozen=True)
class SpendBreakdownResponse:
    lesson_id: str | None
    stage: str
    provider: str
    model: str
    total: SpendTotalResponse


@dataclass(frozen=True)
class LessonSpendResponse:
    lesson_id: str
    total: SpendTotalResponse


@dataclass(frozen=True)
class GenerationStepResponse:
    id: str
    lesson_id: str | None
    stage: str
    started_at: float
    finished_at: float | None
    backend: str | None = None


@dataclass(frozen=True)
class CourseSpendResponse:
    currency: str
    total: SpendTotalResponse
    shared: SpendTotalResponse
    lessons: tuple[LessonSpendResponse, ...]
    breakdown: tuple[SpendBreakdownResponse, ...]
    steps: tuple[GenerationStepResponse, ...] = ()


def total_response(charges: tuple[ModelCharge, ...]) -> SpendTotalResponse:
    total = sum_charges(charges)
    return SpendTotalResponse(
        format(total.known_usd, "f"),
        total.pending_calls,
        total.estimated_calls,
        total.calls,
        total.input_tokens,
        total.output_tokens,
        format(total.credits, "f"),
    )


def spend_response(
    charges: tuple[ModelCharge, ...], steps: tuple[GenerationStep, ...] = ()
) -> CourseSpendResponse:
    lessons = sorted({c.lesson_id for c in charges if c.lesson_id is not None})
    groups = dict.fromkeys((c.lesson_id, c.stage, c.provider, c.model) for c in charges)
    return CourseSpendResponse(
        "USD",
        total_response(charges),
        total_response(tuple(c for c in charges if c.lesson_id is None)),
        tuple(
            LessonSpendResponse(
                key, total_response(tuple(c for c in charges if c.lesson_id == key))
            )
            for key in lessons
        ),
        tuple(
            SpendBreakdownResponse(
                *key,
                total_response(
                    tuple(c for c in charges if (c.lesson_id, c.stage, c.provider, c.model) == key)
                ),
            )
            for key in groups
        ),
        tuple(
            GenerationStepResponse(
                s.id, s.lesson_id, s.stage, s.started_at, s.finished_at, s.backend
            )
            for s in steps
        ),
    )


class GetCourseSpend:
    def __init__(self, courses: CourseRepository, spend: SpendRepository) -> None:
        self._courses, self._spend = courses, spend

    def execute(self, request: SpendRequest) -> CourseSpendResponse:
        self._courses.require_by_id(CourseId(request.course_id))
        return spend_response(
            self._spend.list_by_course_id(request.course_id),
            self._spend.list_steps(course_id=request.course_id),
        )


class RefreshCourseSpend:
    def __init__(
        self, courses: CourseRepository, spend: SpendRepository, billing: Billing, uow: UnitOfWork
    ) -> None:
        self._courses, self._spend, self._billing = courses, spend, billing
        self._uow = uow

    def execute(self, request: SpendRequest) -> CourseSpendResponse:
        with self._uow:
            self._courses.require_by_id(CourseId(request.course_id))
        # The ledger uses short independent operations; no transaction spans provider I/O.
        charges = self._spend.list_by_course_id(request.course_id)
        pending = tuple(
            c
            for c in charges
            if c.usd is None and (c.provider_request_id is not None or c.credits is not None)
        )
        for charge in pending[:100]:
            resolved = self._billing.resolve(charge)
            if resolved != charge:
                self._spend.save(resolved)
        return spend_response(
            self._spend.list_by_course_id(request.course_id),
            self._spend.list_steps(course_id=request.course_id),
        )
