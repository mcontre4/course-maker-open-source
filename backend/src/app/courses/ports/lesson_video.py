from typing import Protocol

from app.courses.domain.animation import AnimationProject
from app.courses.domain.errors import CourseError


class LessonVideoUnavailable(CourseError):
    pass


class LessonVideo(Protocol):
    def read(self, animation: AnimationProject) -> bytes: ...
