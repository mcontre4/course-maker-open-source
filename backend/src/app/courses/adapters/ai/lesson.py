import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict

from httpx import HTTPError
from openai import APIError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.messages import ModelRequest, ToolReturnPart
from pydantic_ai.tools import ToolDefinition
from tavily.errors import (  # type: ignore[import-untyped]
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import TimeoutError as TavilyTimeoutError

from app.courses.adapters.ai.agent_sessions import AgentSessionRun, PersistentAgentSessions
from app.courses.domain.errors import CourseError
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.ports.lesson_agent import (
    LessonAgentRequest,
    LessonAgentResponse,
    LessonGenerationUnavailable,
)

logger = logging.getLogger(__name__)


def validate_plan(ctx: RunContext[LessonAgentRequest], plan: LessonPlan) -> LessonPlan:
    brief = ctx.deps.brief
    if plan.feasibility_status is None:
        raise ModelRetry("Assess lesson feasibility: choose feasible or infeasible")
    try:
        plan.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)
    except CourseError as exc:
        raise ModelRetry(str(exc)) from exc
    # Enforce rounding for new output without invalidating saved recommendations.
    if plan.feasibility_status == "infeasible":
        rounded_minutes = plan.minimum_video_minutes
        if plan.recommended_video_minutes != rounded_minutes:
            raise ModelRetry(
                "Round the total estimated beat duration UP to whole minutes: "
                f"set recommended_video_minutes to {rounded_minutes}"
            )
    if (
        ctx.deps.description
        and plan.feasibility_status == "feasible"
        and sum(beat.seconds for beat in plan.beats) > 600
    ):
        raise ModelRetry("Standalone lessons must not exceed 600 seconds in total")
    validate_outline_size(plan)
    researched_urls = {
        result["url"]
        for message in ctx.messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
        and part.tool_name == "tavily_search"
        and isinstance(part.content, list)
        for result in part.content
        if isinstance(result, dict) and isinstance(result.get("url"), str)
    }
    if not {source.url for source in plan.sources} <= researched_urls:
        raise ModelRetry(
            "Cite only URLs returned by tavily_search; use sources=[] without research"
        )
    return plan


def validate_outline_size(plan: LessonPlan) -> None:
    """Constrain new model output without invalidating previously saved plans."""
    corrections = []
    if len(plan.beats) > 6 or len(plan.examples) != 1 or len(plan.examples[0].steps) > 3:
        corrections.append(
            "Condense the outline to at most six teaching beats and one primary example, "
            "scenario, case or worked problem with at most three short milestones"
        )
    if sum(bool(beat.check_question.strip()) for beat in plan.beats) != 1:
        corrections.append(
            "Include exactly one diagnostic question and expected answer for the whole lesson; "
            "leave both fields empty on all other beats"
        )
    content = [
        *plan.assumed_knowledge,
        *plan.introduced_knowledge,
        *plan.required_facts,
        *plan.equations,
        *plan.misconceptions,
        *plan.scope_boundaries,
        plan.feasibility_explanation,
        plan.recommended_scope_adjustment,
    ]
    if any(len(beat.teaching_notes.split()) > 50 for beat in plan.beats):
        corrections.append("Use 1–3 short teaching-note bullets, at most 50 words per beat")
    for beat in plan.beats:
        content.extend(
            (
                beat.title,
                beat.purpose,
                beat.teaching_notes,
                beat.check_question,
                beat.expected_answer,
            )
        )
    for example in plan.examples:
        content.extend((example.problem, *example.steps, example.result))
    if sum(len(value.split()) for value in content) > 600:
        corrections.append(
            "Condense authored content to at most 600 words; keep outline bullets "
            "and leave detailed explanations and narration to the scripting agent"
        )
    if corrections:
        raise ModelRetry("; ".join(corrections))


class PydanticLessonAgent:
    def __init__(
        self,
        scope: Callable[[], AbstractAsyncContextManager[Agent[LessonAgentRequest, LessonPlan]]],
        model: str,
        sessions: PersistentAgentSessions | None = None,
    ) -> None:
        self._scope, self._model = scope, model
        self._sessions = sessions or PersistentAgentSessions()

    def run(self, request: LessonAgentRequest) -> LessonAgentResponse:
        try:
            return asyncio.run(self._run(request))
        except (
            AgentRunError,
            APIError,
            HTTPError,
            TimeoutError,
            BadRequestError,
            ForbiddenError,
            InvalidAPIKeyError,
            MissingAPIKeyError,
            UsageLimitExceededError,
            TavilyTimeoutError,
        ) as exc:
            logger.warning("Lesson generation provider failure: %s", type(exc).__name__)
            raise LessonGenerationUnavailable(
                "Lesson generation failed; your saved course is unchanged. Please try again"
            ) from exc

    async def _run(self, request: LessonAgentRequest) -> LessonAgentResponse:
        async def turn(state: AgentSessionRun) -> LessonAgentResponse:
            async with self._scope() as agent:
                prompt = asdict(request)
                prompt.pop("session", None)
                if request.session is not None:
                    prompt.pop("conversation", None)
                result = await agent.run(
                    json.dumps(prompt),
                    conversation=state.conversation,
                    deps=request,
                    usage_limits=state.limits(
                        request_limit=12, tool_calls_limit=6, total_tokens_limit=100000
                    ),
                    timeout=180,
                )
                usage = state.capture(result)
                return LessonAgentResponse(
                    result.output,
                    self._model,
                    usage.requests,
                    usage.tool_calls,
                    usage.total_tokens,
                    state.session_id,
                )

        return (await self._sessions.run(request.session, "outline", turn)).output


def prepare_search(
    ctx: RunContext[LessonAgentRequest], tool: "ToolDefinition"
) -> "ToolDefinition | None":
    return None if ctx.usage.tool_calls >= 6 else tool
