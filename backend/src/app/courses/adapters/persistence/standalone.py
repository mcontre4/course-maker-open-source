"""SQLAlchemy storage for lessons without a course foreign key."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.adapters.persistence.codec import _lesson, encode_lesson
from app.courses.adapters.persistence.guide import snapshot_outline
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.identifiers import LessonId
from app.courses.domain.standalone import LessonFlow, LessonOwnerId, LessonTurn, StandaloneLesson
from app.shared.infrastructure.database import Base


class StandaloneLessonRecord(Base):
    __tablename__ = "standalone_lessons"
    __table_args__ = (CheckConstraint("minutes BETWEEN 1 AND 10", name="ck_standalone_minutes"),)
    id: Mapped[str] = mapped_column(String(43), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(41), nullable=False, index=True)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


def encode_standalone(lesson: StandaloneLesson) -> dict[str, Any]:
    data = asdict(lesson)
    data["owner_id"] = str(lesson.owner_id)
    data["content"] = encode_lesson(lesson.content)
    return data


def decode_standalone(data: dict[str, Any]) -> StandaloneLesson:
    return StandaloneLesson(
        LessonOwnerId(data["owner_id"]),
        data["description"],
        _lesson(data["content"]),
        data["revision"],
        data["approved"],
        tuple(LessonTurn(**t) for t in data["turns"]),
        flow=LessonFlow(data.get("flow", "guided")),
    )


class SqlAlchemyStandaloneLessons:
    def __init__(self, session: Session) -> None:
        self._session = session

    def require_by_id(self, lesson_id: LessonId) -> StandaloneLesson:
        return self._require(lesson_id, for_update=False)

    def require_for_change(self, lesson_id: LessonId) -> StandaloneLesson:
        return self._require(lesson_id, for_update=True)

    def _require(self, lesson_id: LessonId, *, for_update: bool) -> StandaloneLesson:
        query = select(StandaloneLessonRecord).where(StandaloneLessonRecord.id == str(lesson_id))
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        record = self._session.scalar(query)
        if record is None:
            raise CourseNotFound("Lesson not found")
        return decode_standalone(record.payload)

    def list_by_owner(
        self, owner_id: LessonOwnerId, limit: int, offset: int
    ) -> tuple[StandaloneLesson, ...]:
        records = self._session.scalars(
            select(StandaloneLessonRecord)
            .where(StandaloneLessonRecord.owner_id == str(owner_id))
            .order_by(StandaloneLessonRecord.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(decode_standalone(record.payload) for record in records)

    def add(self, lesson: StandaloneLesson) -> None:
        self._session.add(
            StandaloneLessonRecord(
                id=str(lesson.content.id),
                owner_id=str(lesson.owner_id),
                minutes=lesson.content.minutes,
                payload=encode_standalone(lesson),
            )
        )

    def save(self, lesson: StandaloneLesson) -> None:
        record = self._session.get(StandaloneLessonRecord, str(lesson.content.id))
        if record is None:
            raise CourseNotFound("Lesson not found")
        previous = record.payload
        old_plan = previous["content"].get("plan")
        new_plan = asdict(lesson.content.plan) if lesson.content.plan else None
        if old_plan != new_plan:
            if old_plan:
                snapshot_outline(
                    self._session,
                    str(lesson.content.id),
                    previous["revision"],
                    json.dumps(old_plan),
                )
            if new_plan:
                snapshot_outline(
                    self._session, str(lesson.content.id), lesson.revision, json.dumps(new_plan)
                )
        record.payload = encode_standalone(lesson)
