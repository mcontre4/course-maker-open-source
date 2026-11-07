import json
from dataclasses import asdict
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, select, update
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import JSON, Text

from app.courses.adapters.persistence.guide import snapshot_outline
from app.courses.domain.curriculum import Curriculum
from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.identifiers import CourseId
from app.courses.ports.syllabus_agent import ConversationTurn, SyllabusConversation
from app.shared.infrastructure.database import Base


class SyllabusConversationRecord(Base):
    agent_session_id: Mapped[str | None] = mapped_column(String(42), nullable=True)
    __tablename__ = "syllabus_conversations"
    __table_args__ = (CheckConstraint("revision > 0", name="ck_syllabus_conversation_revision"),)

    course_id: Mapped[str] = mapped_column(
        String(43), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    history_json: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"))
    curriculum_json: Mapped[str | None] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"))
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class SqlAlchemySyllabusConversations:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_course_id(self, course_id: CourseId) -> SyllabusConversation | None:
        record = self._session.scalar(
            select(SyllabusConversationRecord).where(
                SyllabusConversationRecord.course_id == str(course_id)
            )
        )
        if record is None:
            return None
        return SyllabusConversation(
            record.course_id,
            record.revision,
            record.history_json,
            TypeAdapter(Curriculum).validate_json(record.curriculum_json)
            if record.curriculum_json is not None
            else None,
            tuple(ConversationTurn(**turn) for turn in record.turns),
            record.agent_session_id,
        )

    def save(self, conversation: SyllabusConversation, expected_revision: int) -> None:
        if expected_revision < 0 or conversation.revision != expected_revision + 1:
            raise CourseError("A conversation revision must advance by exactly one")
        previous = self.get_by_course_id(CourseId(conversation.course_id))
        if conversation.curriculum is not None and (
            previous is None or previous.curriculum != conversation.curriculum
        ):
            if previous and previous.curriculum:
                snapshot_outline(
                    self._session,
                    conversation.course_id,
                    previous.revision,
                    json.dumps(asdict(previous.curriculum)),
                )
            snapshot_outline(
                self._session,
                conversation.course_id,
                conversation.revision,
                json.dumps(asdict(conversation.curriculum)),
                "Saved syllabus",
            )
        values = asdict(conversation)
        values.pop("curriculum")
        values["curriculum_json"] = (
            json.dumps(asdict(conversation.curriculum))
            if conversation.curriculum is not None
            else None
        )
        values["turns"] = [asdict(turn) for turn in conversation.turns]
        if expected_revision == 0:
            self._session.add(SyllabusConversationRecord(**values))
            try:
                self._session.flush()
            except IntegrityError as exc:
                if exc.orig is None or not exc.orig.args or exc.orig.args[0] != 1062:
                    raise
                raise CourseConflict("Syllabus conversation changed; reload and retry") from exc
        else:
            result = self._session.connection().execute(
                update(SyllabusConversationRecord)
                .where(
                    SyllabusConversationRecord.course_id == conversation.course_id,
                    SyllabusConversationRecord.revision == expected_revision,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise CourseConflict("Syllabus conversation changed; reload and retry")
