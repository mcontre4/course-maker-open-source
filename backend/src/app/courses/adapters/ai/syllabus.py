import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass

from httpx import HTTPError
from openai import APIError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError, ModelHTTPError
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RunUsage, UsageLimits
from tavily.errors import (  # type: ignore[import-untyped]  # Tavily does not ship typing metadata.
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import (
    TimeoutError as TavilyTimeoutError,
)

from app.courses.adapters.ai.agent_sessions import AgentSessionRun, PersistentAgentSessions
from app.courses.domain.curriculum import Curriculum
from app.courses.domain.duration import Duration
from app.courses.domain.errors import CourseError
from app.courses.ports.syllabus_agent import SyllabusAgentRequest, SyllabusAgentResponse
from app.courses.ports.syllabus_errors import SyllabusUnavailable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentOutput:
    message: str
    curriculum: Curriculum | None


def current_course(ctx: RunContext[str]) -> str:
    remaining = (
        max(0, ctx.usage_limits.tool_calls_limit - ctx.usage.tool_calls)
        if ctx.usage_limits is not None and ctx.usage_limits.tool_calls_limit is not None
        else 0
    )
    return (
        f"Search calls remaining this turn: {remaining}. Research efficiently; when none remain, "
        "finish the complete curriculum using the evidence already gathered.\n"
        "CURRENT COURSE STATE (authoritative saved data):\n" + ctx.deps
    )


def prepare_search(ctx: RunContext[str], tool: ToolDefinition) -> ToolDefinition | None:
    if (
        ctx.usage_limits is not None
        and ctx.usage_limits.tool_calls_limit is not None
        and ctx.usage.tool_calls >= ctx.usage_limits.tool_calls_limit
    ):
        return None
    return tool


def validate_curriculum(ctx: RunContext[str], output: AgentOutput) -> AgentOutput:
    if output.curriculum is not None:
        duration = Duration(**json.loads(ctx.deps)["course"]["duration"])
        try:
            output.curriculum.validate_budget(duration)
        except CourseError as exc:
            raise ModelRetry(str(exc)) from exc
    return output


class PydanticSyllabusAgent:
    def __init__(
        self,
        agent: Agent[str, AgentOutput],
        *,
        timeout: float = 120,
        sessions: PersistentAgentSessions | None = None,
    ) -> None:
        self._agent = agent
        self._timeout = timeout
        self._sessions = sessions or PersistentAgentSessions()

    def run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse:
        return asyncio.run(self._run(request))

    async def _run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse:
        async def turn(state: AgentSessionRun) -> SyllabusAgentResponse:
            conversation = state.conversation
            usage = conversation.usage if conversation is not None else RunUsage()
            try:
                result = await self._agent.run(
                    request.message,
                    conversation=conversation,
                    deps=json.dumps(
                        {
                            "course": asdict(request.course),
                            "curriculum": asdict(request.curriculum)
                            if request.curriculum is not None
                            else None,
                        }
                    ),
                    usage_limits=UsageLimits(
                        request_limit=usage.requests + 12,
                        tool_calls_limit=usage.tool_calls + 6,
                        total_tokens_limit=usage.total_tokens + 150000,
                    ),
                    timeout=self._timeout,
                )
            except (
                AgentRunError,
                ModelHTTPError,
                APIError,
                HTTPError,
                TimeoutError,
                BadRequestError,
                ForbiddenError,
                InvalidAPIKeyError,
                MissingAPIKeyError,
                TavilyTimeoutError,
                UsageLimitExceededError,
            ) as exc:
                logger.warning("Syllabus provider failure: %s", type(exc).__name__)
                raise SyllabusUnavailable("Syllabus generation failed; please try again") from exc
            state.capture(result)
            return SyllabusAgentResponse(
                result.output.message,
                result.output.curriculum,
                state.history_json,
                state.session_id,
            )

        return (
            await self._sessions.run(
                request.session,
                "syllabus",
                turn,
                initial_history=request.history_json if request.session is None else "",
            )
        ).output


class ScopedSyllabusAgent:
    """Create and close provider clients on the event loop that uses them."""

    def __init__(
        self,
        scope: Callable[[], AbstractAsyncContextManager[Agent[str, AgentOutput]]],
        sessions: PersistentAgentSessions | None = None,
    ) -> None:
        self._scope = scope
        self._sessions = sessions

    def run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse:
        return asyncio.run(self._run(request))

    async def _run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse:
        async with self._scope() as agent:
            return await PydanticSyllabusAgent(agent, sessions=self._sessions)._run(request)
