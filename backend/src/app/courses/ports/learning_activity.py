from typing import Protocol

from app.courses.domain.learning_activity import LearningActivity
from app.courses.domain.standalone import LessonOwnerId


class LearningActivities(Protocol):
    def save(self, activity: LearningActivity) -> None: ...
    def recent_by_owner(
        self, owner_id: LessonOwnerId, limit: int
    ) -> tuple[LearningActivity, ...]: ...
