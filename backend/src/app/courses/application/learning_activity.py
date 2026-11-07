from dataclasses import dataclass

from app.courses.domain.learning_activity import LearningActivity, learning_item_id
from app.courses.domain.standalone import LessonOwnerId
from app.courses.ports.learning_activity import LearningActivities
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock


@dataclass(frozen=True)
class RecordLearningActivityRequest:
    owner_id: str
    item_id: str


class RecordLearningActivity:
    def __init__(self, activities: LearningActivities, clock: Clock, uow: UnitOfWork) -> None:
        self._activities, self._clock, self._uow = activities, clock, uow

    def execute(self, request: RecordLearningActivityRequest) -> None:
        activity = LearningActivity(
            LessonOwnerId(request.owner_id),
            learning_item_id(request.item_id),
            self._clock.now().isoformat(),
        )
        with self._uow:
            self._activities.save(activity)
            self._uow.commit()


@dataclass(frozen=True)
class GetLearningActivityRequest:
    owner_id: str
    limit: int


@dataclass(frozen=True)
class LearningActivityItemResponse:
    item_id: str
    last_opened_at: str


@dataclass(frozen=True)
class LearningActivityResponse:
    items: tuple[LearningActivityItemResponse, ...]


class GetLearningActivity:
    def __init__(self, activities: LearningActivities) -> None:
        self._activities = activities

    def execute(self, request: GetLearningActivityRequest) -> LearningActivityResponse:
        recent = self._activities.recent_by_owner(LessonOwnerId(request.owner_id), request.limit)
        return LearningActivityResponse(
            tuple(
                LearningActivityItemResponse(str(item.item_id), item.last_opened_at)
                for item in recent
            )
        )
