from pydantic import TypeAdapter

from app.courses.domain.curriculum import Curriculum
from app.courses.domain.lesson_plan import LessonPlan


class PydanticGuideOutlineCodec:
    def decode_plan(self, value: str) -> LessonPlan:
        return TypeAdapter(LessonPlan).validate_json(value)

    def decode_curriculum(self, value: str) -> Curriculum:
        return TypeAdapter(Curriculum).validate_json(value)
