from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.agent_session import AgentSession, AgentSessionId


@dataclass(frozen=True)
class AgentSessionContext:
    owner_id: str
    resource_id: str | None = None
    job_id: str | None = None
    session_id: str | None = None


class AgentSessions(Protocol):
    def require_by_id(self, session_id: AgentSessionId) -> AgentSession: ...

    def add(self, session: AgentSession) -> None: ...

    def save(self, session: AgentSession, expected_revision: int) -> None: ...
