from dataclasses import asdict
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    cast,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.adapters.persistence.codec import decode
from app.courses.adapters.persistence.models import CourseRecord
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord, decode_standalone
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_interactive import (
    InteractiveBuild,
    InteractiveDetails,
    InteractiveFailure,
    InteractiveId,
    InteractiveLesson,
    InteractiveVersion,
    LessonInteractive,
)
from app.shared.infrastructure.database import Base


class LessonInteractiveRecord(Base):
    __tablename__ = "lesson_interactives"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_lesson_interactive_revision"),
        CheckConstraint("slot BETWEEN 1 AND 10", name="ck_lesson_interactive_slot"),
        CheckConstraint(
            "(standalone_lesson_id IS NOT NULL AND standalone_lesson_id = lesson_id "
            "AND course_id IS NULL) OR "
            "(standalone_lesson_id IS NULL AND course_id IS NOT NULL)",
            name="ck_lesson_interactive_parent",
        ),
        UniqueConstraint("lesson_id", "slot", name="uq_lesson_interactive_slot"),
        Index("ix_lesson_interactive_order", "lesson_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(String(43), nullable=False)
    standalone_lesson_id: Mapped[str | None] = mapped_column(
        String(43), ForeignKey("standalone_lessons.id", ondelete="CASCADE"), nullable=True
    )
    course_id: Mapped[str | None] = mapped_column(
        String(43), ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    __mapper_args__ = {"version_id_col": revision, "version_id_generator": False}


def encode_interactive(item: LessonInteractive) -> dict[str, Any]:
    payload = asdict(item)
    payload["id"], payload["lesson_id"] = str(item.id), str(item.lesson_id)
    return payload


def decode_interactive(data: dict[str, Any]) -> LessonInteractive:
    return LessonInteractive(
        InteractiveId(data["id"]),
        LessonId(data["lesson_id"]),
        data["brief"],
        InteractiveDetails(
            data["details"]["title"], data["details"]["goal"], tuple(data["details"]["prompts"])
        ),
        data["created_at"],
        data["updated_at"],
        data["revision"],
        tuple(InteractiveVersion(**v) for v in data["versions"]),
        data["current_version"],
        data["published_version"],
        InteractiveBuild(**data["build"]) if data["build"] else None,
        InteractiveFailure(**data["failure"]) if data["failure"] else None,
        GenerationMode(data["generation_mode"]),
        details_customized=data.get("details_customized", False),
    )


class SqlAlchemyInteractiveLessons:
    """Resolve either parent by the globally unique lesson ID.

    Course lessons currently live inside the course JSON aggregate. Locking the
    parent serializes collection writes without holding locks during generation.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def require_by_id(self, lesson_id: LessonId) -> InteractiveLesson:
        return self._require(lesson_id, for_update=False)

    def require_for_change(self, lesson_id: LessonId) -> InteractiveLesson:
        return self._require(lesson_id, for_update=True)

    def _require(self, lesson_id: LessonId, *, for_update: bool) -> InteractiveLesson:
        query = select(StandaloneLessonRecord).where(StandaloneLessonRecord.id == str(lesson_id))
        if for_update:
            query = query.with_for_update()
        record = self._session.scalar(query.execution_options(populate_existing=True))
        if record:
            standalone = decode_standalone(record.payload)
            audience = standalone.content.style.audience if standalone.content.style else ""
            return InteractiveLesson(
                standalone.content,
                str(standalone.owner_id),
                standalone.description,
                audience or "Adapt to the learner description",
            )
        # Filter candidates in SQL, then verify current membership rather than matching history.
        candidates = select(CourseRecord).where(
            cast(CourseRecord.payload, Text).contains(str(lesson_id), autoescape=True)
        )
        if for_update:
            candidates = candidates.with_for_update()
        for parent in self._session.scalars(candidates.execution_options(populate_existing=True)):
            course = decode(parent.payload)
            for chapter in course.chapters:
                for lesson in chapter.lessons:
                    if lesson.id == lesson_id:
                        style = lesson.style or course.style
                        return InteractiveLesson(
                            lesson,
                            course.owner_id,
                            course.description,
                            style.audience if style else "",
                            str(course.id),
                        )
        raise CourseNotFound("Lesson not found")


class SqlAlchemyLessonInteractives:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_lesson_id(self, lesson_id: LessonId) -> tuple[LessonInteractive, ...]:
        records = self._session.scalars(
            select(LessonInteractiveRecord)
            .where(LessonInteractiveRecord.lesson_id == str(lesson_id))
            .order_by(LessonInteractiveRecord.position, LessonInteractiveRecord.id)
            .execution_options(populate_existing=True)
        )
        return tuple(decode_interactive(r.payload) for r in records)

    def get_by_id(self, identifier: InteractiveId) -> LessonInteractive | None:
        record = self._session.get(LessonInteractiveRecord, str(identifier), populate_existing=True)
        return decode_interactive(record.payload) if record else None

    def add(self, interactive: LessonInteractive, lesson: InteractiveLesson) -> None:
        records = tuple(
            self._session.scalars(
                select(LessonInteractiveRecord).where(
                    LessonInteractiveRecord.lesson_id == str(interactive.lesson_id)
                )
            )
        )
        slots = {r.slot for r in records}
        slot = next((s for s in range(1, 11) if s not in slots), None)
        if slot is None:
            raise CourseConflict("A lesson can have up to 10 interactives.")
        self._session.add(
            LessonInteractiveRecord(
                id=str(interactive.id),
                lesson_id=str(interactive.lesson_id),
                standalone_lesson_id=None if lesson.course_id else str(interactive.lesson_id),
                course_id=lesson.course_id,
                slot=slot,
                position=max((r.position for r in records), default=-1) + 1,
                revision=interactive.revision,
                payload=encode_interactive(interactive),
            )
        )

    def save(self, interactive: LessonInteractive) -> None:
        record = self._session.get(LessonInteractiveRecord, str(interactive.id))
        if record is None:
            raise CourseNotFound("Interactive not found")
        record.revision, record.payload = interactive.revision, encode_interactive(interactive)

    def delete(self, interactive: LessonInteractive) -> None:
        record = self._session.get(LessonInteractiveRecord, str(interactive.id))
        if record:
            self._session.delete(record)

    def reorder(self, lesson_id: LessonId, identifiers: tuple[InteractiveId, ...]) -> None:
        for position, identifier in enumerate(identifiers):
            record = self._session.get(LessonInteractiveRecord, str(identifier))
            if record is None or record.lesson_id != str(lesson_id):
                raise CourseNotFound("Interactive not found")
            record.position = position
