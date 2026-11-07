from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from app.courses.domain.agent_session import AgentSession, AgentSessionId
from app.courses.domain.errors import CourseNotFound
from app.courses.ports.agent_sessions import AgentSessionContext, AgentSessions
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class AgentTurnResponse[T]:
    output: T
    history_json: str


@dataclass(frozen=True)
class RunAgentSessionRequest[T]:
    context: AgentSessionContext
    agent: str
    run: Callable[[str, str], Awaitable[AgentTurnResponse[T]]]


@dataclass(frozen=True)
class RunAgentSessionResponse[T]:
    output: T
    session_id: str


class RunAgentSession:
    def __init__(self, sessions: AgentSessions, uow: UnitOfWork, ids: IdGenerator) -> None:
        self._sessions, self._uow, self._ids = sessions, uow, ids

    async def execute[T](self, request: RunAgentSessionRequest[T]) -> RunAgentSessionResponse[T]:
        scope = request.context
        with self._uow:
            if scope.session_id is not None:
                try:
                    session_id = AgentSessionId(scope.session_id)
                except ValueError as exc:
                    raise CourseNotFound("Agent session not found") from exc
                session = self._sessions.require_by_id(session_id)
                session.require_scope(
                    scope.owner_id, request.agent, scope.resource_id, scope.job_id
                )
            else:
                session = AgentSession(
                    AgentSessionId.new(self._ids),
                    scope.owner_id,
                    request.agent,
                    scope.resource_id,
                    scope.job_id,
                )
        # No database transaction stays open during the model or its tools.
        result = await request.run(str(session.id), session.history_json)
        updated = session.advance(result.history_json)
        with self._uow:
            if scope.session_id is None:
                self._sessions.add(updated)
            else:
                self._sessions.save(updated, session.revision)
            self._uow.commit()
        return RunAgentSessionResponse(result.output, str(session.id))


type AgentSessionFactory = Callable[[], AbstractContextManager[RunAgentSession]]
