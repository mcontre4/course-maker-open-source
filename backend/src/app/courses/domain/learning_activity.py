"""When a person last opened one of their courses or lessons."""

from dataclasses import dataclass

from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.standalone import LessonOwnerId
from app.shared.domain.errors import InvalidIdentifierError


def learning_item_id(value: str) -> CourseId | LessonId:
    if value.startswith(CourseId.prefix):
        return CourseId(value)
    if value.startswith(LessonId.prefix):
        return LessonId(value)
    raise InvalidIdentifierError("Only courses and lessons can be opened.")


@dataclass(frozen=True)
class LearningActivity:
    owner_id: LessonOwnerId
    item_id: CourseId | LessonId
    last_opened_at: str
