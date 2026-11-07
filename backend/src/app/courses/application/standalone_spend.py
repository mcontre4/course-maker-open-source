from app.courses.application.spend import CourseSpendResponse, spend_response
from app.courses.application.standalone import _StandaloneUseCase
from app.courses.application.standalone_dto import StandaloneLessonRequest
from app.courses.ports.spend import Billing, SpendRepository
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.shared.application.unit_of_work import UnitOfWork


class GetStandaloneSpend(_StandaloneUseCase):
    def __init__(self, lessons: StandaloneLessons, uow: UnitOfWork, spend: SpendRepository) -> None:
        super().__init__(lessons, uow)
        self._spend = spend

    def execute(self, request: StandaloneLessonRequest) -> CourseSpendResponse:
        with self._uow:
            self._load(request.lesson_id, request.owner_id)
        return spend_response(
            self._spend.list_by_lesson_id(request.lesson_id),
            self._spend.list_steps(lesson_id=request.lesson_id),
        )


class RefreshStandaloneSpend(_StandaloneUseCase):
    def __init__(
        self, lessons: StandaloneLessons, uow: UnitOfWork, spend: SpendRepository, billing: Billing
    ) -> None:
        super().__init__(lessons, uow)
        self._spend, self._billing = spend, billing

    def execute(self, request: StandaloneLessonRequest) -> CourseSpendResponse:
        with self._uow:
            self._load(request.lesson_id, request.owner_id)
        charges = self._spend.list_by_lesson_id(request.lesson_id)
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
            self._spend.list_by_lesson_id(request.lesson_id),
            self._spend.list_steps(lesson_id=request.lesson_id),
        )
