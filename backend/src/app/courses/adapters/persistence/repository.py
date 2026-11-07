from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.codec import decode, encode
from app.courses.adapters.persistence.lesson_interactive import LessonInteractiveRecord
from app.courses.adapters.persistence.models import CourseRecord
from app.courses.domain.course import Course
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.identifiers import CourseId


class MySqlCourseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._loaded: dict[str, CourseRecord] = {}

    def get_by_id(self, course_id: CourseId) -> Course | None:
        record = self._session.get(CourseRecord, str(course_id))
        if record is not None:
            self._loaded[str(course_id)] = record
        return decode(record.payload) if record else None

    def require_by_id(self, course_id: CourseId) -> Course:
        course = self.get_by_id(course_id)
        if course is None:
            raise CourseNotFound("Course not found")
        return course

    def require_for_syllabus_change(self, course_id: CourseId) -> Course:
        record = self._session.scalar(
            select(CourseRecord).where(CourseRecord.id == str(course_id)).with_for_update()
        )
        if record is None:
            raise CourseNotFound("Course not found")
        self._loaded[str(course_id)] = record
        return decode(record.payload)

    def _query(self, search: str, status: str | None) -> Select[tuple[CourseRecord]]:
        query = select(CourseRecord)
        if search.strip():
            query = query.where(CourseRecord.title.contains(search.strip(), autoescape=True))
        if status is not None:
            query = query.where(CourseRecord.status == status)
        return query

    def list_courses(
        self, search: str, status: str | None, limit: int, offset: int
    ) -> tuple[Course, ...]:
        records = self._session.scalars(
            self._query(search, status)
            .order_by(CourseRecord.title, CourseRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(decode(record.payload) for record in records)

    def count_courses(self, search: str, status: str | None) -> int:
        return (
            self._session.scalar(
                select(func.count()).select_from(self._query(search, status).subquery())
            )
            or 0
        )

    def list_by_owner(
        self, owner_id: str, search: str, status: str | None, limit: int, offset: int
    ) -> tuple[Course, ...]:
        records = self._session.scalars(
            self._query(search, status)
            .where(
                CourseRecord.payload["owner_id"].as_string() == owner_id,
            )
            .order_by(CourseRecord.title, CourseRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(decode(record.payload) for record in records)

    def count_by_owner(self, owner_id: str, search: str, status: str | None) -> int:
        query = self._query(search, status).where(
            CourseRecord.payload["owner_id"].as_string() == owner_id,
        )
        return self._session.scalar(select(func.count()).select_from(query.subquery())) or 0

    def add(self, course: Course) -> None:
        self._session.add(
            CourseRecord(
                id=str(course.id), title=course.title, status=course.status, payload=encode(course)
            )
        )

    def save(self, course: Course) -> None:
        record = self._loaded.get(str(course.id)) or self._session.get(CourseRecord, str(course.id))
        if record is None:
            raise CourseNotFound("Course not found")
        # Course lessons are nested JSON, so membership removal cannot use a lesson FK.
        lesson_ids = {str(lesson.id) for chapter in course.chapters for lesson in chapter.lessons}
        previous = decode(record.payload)
        removed = {
            str(lesson.id) for chapter in previous.chapters for lesson in chapter.lessons
        } - lesson_ids
        record.title, record.status, record.payload = course.title, course.status, encode(course)
        if removed:
            # Acquire the parent write lock before deleting child rows, matching
            # the lock order used by interactive mutations.
            self._session.flush()
            self._session.execute(
                delete(LessonInteractiveRecord).where(
                    LessonInteractiveRecord.course_id == str(course.id),
                    LessonInteractiveRecord.lesson_id.in_(removed),
                )
            )

    def delete(self, course: Course) -> None:
        record = self._loaded.get(str(course.id)) or self._session.get(CourseRecord, str(course.id))
        if record is None:
            raise CourseNotFound("Course not found")
        self._session.delete(record)
