from sqlalchemy import CheckConstraint, Integer, String, Text, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.courses.domain.agent_session import AgentSession, AgentSessionId
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.shared.infrastructure.database import Base


class AgentSessionRecord(Base):
    __tablename__ = "agent_sessions"
    __table_args__ = (CheckConstraint("revision > 0", name="ck_agent_session_revision"),)
    id: Mapped[str] = mapped_column(String(42), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    agent: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100), index=True)
    job_id: Mapped[str | None] = mapped_column(String(100), index=True)
    history_json: Mapped[str] = mapped_column(Text().with_variant(Text(length=4294967295), "mysql"))
    revision: Mapped[int] = mapped_column(Integer)


class SqlAlchemyAgentSessions:
    def __init__(self, session: Session) -> None:
        self._session = session

    def require_by_id(self, session_id: AgentSessionId) -> AgentSession:
        record = self._session.get(AgentSessionRecord, str(session_id), populate_existing=True)
        if record is None:
            raise CourseNotFound("Agent session not found")
        return AgentSession(
            AgentSessionId(record.id),
            record.owner_id,
            record.agent,
            record.resource_id,
            record.job_id,
            record.history_json,
            record.revision,
        )

    def add(self, session: AgentSession) -> None:
        self._session.add(
            AgentSessionRecord(
                id=str(session.id),
                owner_id=session.owner_id,
                agent=session.agent,
                resource_id=session.resource_id,
                job_id=session.job_id,
                history_json=session.history_json,
                revision=session.revision,
            )
        )
        self._session.flush()

    def save(self, session: AgentSession, expected_revision: int) -> None:
        if session.revision != expected_revision + 1:
            raise CourseConflict("An agent session revision must advance by one")
        result = self._session.connection().execute(
            update(AgentSessionRecord)
            .where(
                AgentSessionRecord.id == str(session.id),
                AgentSessionRecord.owner_id == session.owner_id,
                AgentSessionRecord.agent == session.agent,
                AgentSessionRecord.resource_id == session.resource_id,
                AgentSessionRecord.job_id == session.job_id,
                AgentSessionRecord.revision == expected_revision,
            )
            .values(history_json=session.history_json, revision=session.revision)
        )
        if result.rowcount != 1:
            raise CourseConflict("Agent session changed concurrently; reload and retry")
