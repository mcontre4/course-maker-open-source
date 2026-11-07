"""Authorize access before any private course operation, including provider jobs."""

from dataclasses import dataclass

from app.courses.domain.errors import CourseNotFound
from app.courses.domain.identifiers import CourseId
from app.courses.ports.course_repository import CourseRepository


@dataclass(frozen=True, slots=True)
class AuthorizeCourseRequest:
    course_id: str
    owner_id: str


@dataclass(frozen=True, slots=True)
class AuthorizeCourseResponse:
    allowed: bool = True


class AuthorizeCourseAccess:
    def __init__(self, courses: CourseRepository) -> None:
        self._courses = courses

    def execute(self, request: AuthorizeCourseRequest) -> AuthorizeCourseResponse:
        course = self._courses.get_by_id(CourseId(request.course_id))
        if course is None or course.owner_id != request.owner_id:
            raise CourseNotFound("Course not found")
        return AuthorizeCourseResponse()
