from collections.abc import Iterator
from heapq import nsmallest
from itertools import islice

from sqlalchemy import String, Text, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.adapters.persistence.codec import decode
from app.courses.adapters.persistence.models import CourseRecord
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord, decode_standalone
from app.courses.domain.content_search import matches_search, search_rank
from app.courses.domain.course import Course
from app.courses.domain.creator import CreatorProfile
from app.courses.domain.identifiers import LessonId
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.shared.infrastructure.database import Base


class CreatorRecord(Base):
    __tablename__ = "creator_profiles"
    id: Mapped[str] = mapped_column(String(41), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    picture: Mapped[str | None] = mapped_column(
        Text().with_variant(Text(length=16777215), "mysql"), nullable=True
    )


class SqlAlchemyCreators:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, creator_id: LessonOwnerId) -> CreatorProfile | None:
        record = self._session.get(CreatorRecord, str(creator_id))
        return CreatorProfile(creator_id, record.name, record.picture) if record else None

    def add(self, profile: CreatorProfile) -> None:
        values = {"id": str(profile.id), "name": profile.name, "picture": profile.picture}
        if self._session.get_bind().dialect.name == "postgresql":
            statement = postgres_insert(CreatorRecord).values(**values)
            self._session.execute(statement.on_conflict_do_nothing(index_elements=["id"]))
        else:
            insert = mysql_insert(CreatorRecord).values(**values)
            self._session.execute(insert.on_duplicate_key_update(id=insert.inserted.id))

    def save(self, profile: CreatorProfile) -> None:
        self.add(profile)
        self._session.execute(
            update(CreatorRecord)
            .where(CreatorRecord.id == str(profile.id))
            .values(name=profile.name, picture=profile.picture)
        )

    def courses_by_creator(self, creator_id: LessonOwnerId) -> tuple[Course, ...]:
        records = self._session.scalars(
            select(CourseRecord)
            .where(CourseRecord.payload["owner_id"].as_string() == str(creator_id))
            .order_by(CourseRecord.title, CourseRecord.id)
        )
        return tuple(decode(record.payload) for record in records)

    def lessons_by_creator(self, creator_id: LessonOwnerId) -> tuple[StandaloneLesson, ...]:
        records = self._session.scalars(
            select(StandaloneLessonRecord)
            .where(StandaloneLessonRecord.owner_id == str(creator_id))
            .order_by(StandaloneLessonRecord.id)
        )
        return tuple(decode_standalone(record.payload) for record in records)

    def get_lesson(self, lesson_id: LessonId) -> StandaloneLesson | None:
        record = self._session.get(StandaloneLessonRecord, str(lesson_id))
        return decode_standalone(record.payload) if record else None

    def latest_courses(self, limit: int, query: str = "") -> tuple[Course, ...]:
        statement = (
            select(CourseRecord)
            .order_by(CourseRecord.created_at.desc(), CourseRecord.id.desc())
            .execution_options(yield_per=50)
        )
        with self._session.scalars(statement) as records:

            def matching() -> Iterator[Course]:
                for record in records:
                    course = decode(record.payload)
                    published = tuple(
                        lesson
                        for chapter in course.chapters
                        for lesson in chapter.lessons
                        if lesson.is_published
                    )
                    if published and (
                        matches_search(query, course.title, course.description)
                        or any(matches_search(query, lesson.title) for lesson in published)
                    ):
                        yield course

            if not query:
                return tuple(islice(matching(), limit))
            return tuple(
                nsmallest(
                    limit,
                    matching(),
                    key=lambda course: min(
                        search_rank(query, course.title),
                        *(
                            search_rank(query, lesson.title)
                            for chapter in course.chapters
                            for lesson in chapter.lessons
                            if lesson.is_published
                        ),
                    ),
                )
            )

    def latest_lessons(self, limit: int, query: str = "") -> tuple[StandaloneLesson, ...]:
        statement = (
            select(StandaloneLessonRecord)
            .order_by(StandaloneLessonRecord.created_at.desc(), StandaloneLessonRecord.id.desc())
            .execution_options(yield_per=50)
        )
        with self._session.scalars(statement) as records:

            def matching() -> Iterator[StandaloneLesson]:
                for record in records:
                    lesson = decode_standalone(record.payload)
                    if lesson.content.is_published and matches_search(query, lesson.content.title):
                        yield lesson

            if not query:
                return tuple(islice(matching(), limit))
            return tuple(
                nsmallest(
                    limit, matching(), key=lambda lesson: search_rank(query, lesson.content.title)
                )
            )
