from app.courses.domain.course import Course
from app.courses.domain.identifiers import CourseId
from app.courses.ports.course_repository import CourseRepository
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


class _CourseUseCase:
    def __init__(
        self, courses: CourseRepository, unit_of_work: UnitOfWork, id_generator: IdGenerator
    ) -> None:
        self._courses = courses
        self._uow = unit_of_work
        self._ids = id_generator

    def _get(self, course_id: str) -> Course:
        return self._courses.require_by_id(CourseId(course_id))
