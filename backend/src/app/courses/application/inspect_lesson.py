from dataclasses import dataclass

from app.courses.application.spend import CourseSpendResponse, spend_response
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.spend import generation_seconds
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.spend import Billing, SpendRepository
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock


@dataclass(frozen=True)
class InspectLessonRequest:
    lesson_id: str
    course_id: str | None = None
    refresh: bool = False


@dataclass(frozen=True)
class InspectLessonResponse:
    lesson_id: str
    course_id: str | None
    title: str
    spend: CourseSpendResponse
    generation_seconds: float | None
    generation_active: bool


class InspectLesson:
    """Internal diagnostics; the incoming adapter authorizes staff access."""

    def __init__(
        self,
        lessons: StandaloneLessons,
        courses: CourseRepository,
        uow: UnitOfWork,
        spend: SpendRepository,
        billing: Billing,
        clock: Clock,
    ) -> None:
        self._lessons, self._courses, self._uow = lessons, courses, uow
        self._spend, self._billing, self._clock = spend, billing, clock

    def execute(self, request: InspectLessonRequest) -> InspectLessonResponse:
        with self._uow:
            if request.course_id is None:
                title = self._lessons.require_by_id(LessonId(request.lesson_id)).content.title
            else:
                course = self._courses.require_by_id(CourseId(request.course_id))
                title = course.lesson(request.lesson_id).title
        # Ledger reads and provider reconciliation happen outside the content transaction.
        charges = (
            self._spend.list_by_lesson_id(request.lesson_id)
            if request.course_id is None
            else tuple(
                charge
                for charge in self._spend.list_by_course_id(request.course_id)
                if charge.lesson_id == request.lesson_id
            )
        )
        if request.refresh:
            pending = tuple(
                charge
                for charge in charges
                if charge.usd is None
                and (charge.provider_request_id is not None or charge.credits is not None)
            )
            for charge in pending[:100]:
                resolved = self._billing.resolve(charge)
                if resolved != charge:
                    self._spend.save(resolved)
            charges = tuple(
                charge
                for charge in (
                    self._spend.list_by_lesson_id(request.lesson_id)
                    if request.course_id is None
                    else self._spend.list_by_course_id(request.course_id)
                )
                if charge.lesson_id == request.lesson_id
            )
        steps = tuple(
            step
            for step in self._spend.list_steps(
                course_id=request.course_id, lesson_id=request.lesson_id
            )
            if step.lesson_id == request.lesson_id
        )
        return InspectLessonResponse(
            request.lesson_id,
            request.course_id,
            title,
            spend_response(charges, steps),
            generation_seconds(steps, self._clock.now().timestamp()),
            any(step.finished_at is None for step in steps),
        )
