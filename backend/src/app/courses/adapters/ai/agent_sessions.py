from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace

from pydantic_ai import AgentRunResult, Conversation, ConversationTypeAdapter
from pydantic_ai.usage import RunUsage, UsageLimits

from app.courses.application.run_agent_session import (
    AgentSessionFactory,
    AgentTurnResponse,
    RunAgentSessionRequest,
)
from app.courses.domain.errors import CourseConflict
from app.courses.ports.agent_sessions import AgentSessionContext

SessionFactory = AgentSessionFactory


@dataclass
class AgentSessionRun:
    conversation: Conversation | None
    session_id: str | None = None
    history_json: str = ""
    _usage_before: RunUsage = field(init=False)

    def __post_init__(self) -> None:
        self._usage_before = replace(self.conversation.usage) if self.conversation else RunUsage()

    def capture[T](self, result: AgentRunResult[T]) -> RunUsage:
        self.history_json = ConversationTypeAdapter.dump_json(result.conversation).decode()
        return result.usage - self._usage_before

    def limits(
        self,
        *,
        request_limit: int,
        total_tokens_limit: int,
        tool_calls_limit: int | None = None,
    ) -> UsageLimits:
        usage = self.conversation.usage if self.conversation else RunUsage()
        return UsageLimits(
            request_limit=usage.requests + request_limit,
            total_tokens_limit=usage.total_tokens + total_tokens_limit,
            tool_calls_limit=usage.tool_calls + tool_calls_limit
            if tool_calls_limit is not None
            else None,
        )


@dataclass(frozen=True)
class SessionResult[T]:
    output: T
    session_id: str | None


class PersistentAgentSessions:
    def __init__(self, factory: SessionFactory | None = None) -> None:
        self._factory = factory

    async def run[T](
        self,
        context: AgentSessionContext | None,
        agent: str,
        run: Callable[[AgentSessionRun], Awaitable[T]],
        *,
        initial_history: str = "",
    ) -> SessionResult[T]:
        if context is not None and context.session_id is not None and self._factory is None:
            raise CourseConflict("Agent session persistence is not configured; cannot resume")
        if context is None or self._factory is None:
            state = AgentSessionRun(
                ConversationTypeAdapter.validate_json(initial_history)
                if initial_history and initial_history != "[]"
                else None
            )
            return SessionResult(await run(state), None)

        async def invoke(session_id: str, history: str) -> AgentTurnResponse[T]:
            stored = history or initial_history
            conversation = (
                ConversationTypeAdapter.validate_json(stored)
                if stored and stored != "[]"
                else Conversation(conversation_id=session_id)
            )
            # Imported legacy conversations acquire this durable application's identity.
            conversation = replace(conversation, conversation_id=session_id)
            state = AgentSessionRun(conversation, session_id)
            output = await run(state)
            return AgentTurnResponse(output, state.history_json)

        with self._factory() as use_case:
            result = await use_case.execute(RunAgentSessionRequest(context, agent, invoke))
        return SessionResult(result.output, result.session_id)
