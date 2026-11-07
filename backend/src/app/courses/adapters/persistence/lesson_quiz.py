from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_quiz import (
    LessonQuiz,
    LessonQuizAttempt,
    LessonQuizAttemptId,
    LessonQuizQuestion,
)
from app.shared.infrastructure.database import Base


class LessonQuizRecord(Base):
    __tablename__ = "lesson_quizzes"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_lesson_quiz_revision"),)

    lesson_id: Mapped[str] = mapped_column(
        String(43), ForeignKey("standalone_lessons.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class LessonQuizAttemptRecord(Base):
    __tablename__ = "lesson_quiz_attempts"
    __table_args__ = (
        Index("ix_lesson_quiz_attempt_learner", "lesson_id", "learner_id"),
        CheckConstraint(
            "score >= 0 AND score <= total AND total BETWEEN 1 AND 20",
            name="ck_lesson_quiz_attempt_score",
        ),
        CheckConstraint("quiz_revision >= 1", name="ck_lesson_quiz_attempt_revision"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(
        String(43), ForeignKey("standalone_lessons.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    quiz_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


def encode_quiz(quiz: LessonQuiz) -> dict[str, Any]:
    return {
        "questions": [asdict(q) for q in quiz.questions],
        "origin": quiz.origin,
        "session_id": quiz.session_id,
    }


def decode_quiz(lesson_id: str, revision: int, payload: dict[str, Any]) -> LessonQuiz:
    return LessonQuiz(
        LessonId(lesson_id),
        tuple(
            LessonQuizQuestion(
                q["id"],
                q["kind"],
                q["prompt"],
                tuple(q["options"]),
                q["correct_index"],
                q["explanation"],
            )
            for q in payload["questions"]
        ),
        payload["origin"],
        revision,
        payload.get("session_id"),
    )


class SqlAlchemyLessonQuizzes:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_lesson_id(self, lesson_id: LessonId) -> LessonQuiz | None:
        record = self._session.get(LessonQuizRecord, str(lesson_id), populate_existing=True)
        return decode_quiz(record.lesson_id, record.revision, record.payload) if record else None

    def save(self, quiz: LessonQuiz) -> None:
        record = self._session.get(LessonQuizRecord, str(quiz.lesson_id))
        if record is None:
            self._session.add(
                LessonQuizRecord(
                    lesson_id=str(quiz.lesson_id), revision=quiz.revision, payload=encode_quiz(quiz)
                )
            )
        else:
            record.revision, record.payload = quiz.revision, encode_quiz(quiz)

    def add_attempt(self, attempt: LessonQuizAttempt) -> None:
        self._session.add(
            LessonQuizAttemptRecord(
                id=str(attempt.id),
                lesson_id=str(attempt.quiz.lesson_id),
                learner_id=attempt.learner_id,
                quiz_revision=attempt.quiz.revision,
                score=attempt.score,
                total=len(attempt.quiz.questions),
                passed=attempt.passed,
                submitted_at=datetime.fromisoformat(attempt.submitted_at),
                payload={
                    "quiz": encode_quiz(attempt.quiz),
                    "answers": list(attempt.answers),
                    "submitted_at": attempt.submitted_at,
                },
            )
        )

    def list_attempts(
        self, lesson_id: LessonId, learner_id: str, limit: int, offset: int
    ) -> tuple[LessonQuizAttempt, ...]:
        records = self._session.scalars(
            select(LessonQuizAttemptRecord)
            .where(
                LessonQuizAttemptRecord.lesson_id == str(lesson_id),
                LessonQuizAttemptRecord.learner_id == learner_id,
            )
            .order_by(
                LessonQuizAttemptRecord.submitted_at.desc(), LessonQuizAttemptRecord.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(
            LessonQuizAttempt(
                LessonQuizAttemptId(r.id),
                r.learner_id,
                decode_quiz(r.lesson_id, r.quiz_revision, r.payload["quiz"]),
                tuple(r.payload["answers"]),
                r.payload["submitted_at"],
            )
            for r in records
        )
