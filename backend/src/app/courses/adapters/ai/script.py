"""The narration-only provider boundary; no storyboard or animation output schema."""

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict

from httpx import HTTPError
from openai import APIError
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError

from app.courses.adapters.ai.agent_sessions import AgentSessionRun, PersistentAgentSessions
from app.courses.domain.errors import CourseError
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.script import LessonScript, ScriptSegment
from app.courses.ports.script_agent import ScriptAgentRequest, ScriptAgentResponse
from app.courses.ports.storyboard_agent import StoryboardGenerationUnavailable


class ScriptSegmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: str
    teaching_beat_index: int
    learning_purpose: str
    narration_text: str
    target_duration_sec: int
    equations: list[str]
    visual_intent: str


class ScriptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    lesson_id: str
    objectives: list[str]
    target_video_minutes: int
    segments: list[ScriptSegmentOutput]

    def to_domain(self) -> LessonScript:
        return LessonScript(
            self.lesson_id,
            tuple(self.objectives),
            self.target_video_minutes,
            tuple(
                ScriptSegment(
                    s.scene_id,
                    s.teaching_beat_index,
                    s.learning_purpose,
                    s.narration_text,
                    s.target_duration_sec,
                    tuple(s.equations),
                    s.visual_intent,
                )
                for s in self.segments
            ),
        )


def validate_script(ctx: RunContext[ScriptAgentRequest], output: ScriptOutput) -> ScriptOutput:
    try:
        output.to_domain().validate_plan(ctx.deps.plan, ctx.deps.target_video_minutes)
    except CourseError as exc:
        raise ModelRetry(str(exc)) from exc
    return output


class PydanticScriptAgent:
    def __init__(
        self,
        scope: Callable[[], AbstractAsyncContextManager[Agent[ScriptAgentRequest, ScriptOutput]]],
        model: str,
        sessions: PersistentAgentSessions | None = None,
    ) -> None:
        self._scope, self._model = scope, model
        self._sessions = sessions or PersistentAgentSessions()

    def run(self, request: ScriptAgentRequest) -> ScriptAgentResponse:
        try:
            return asyncio.run(self._run(request))
        except (AgentRunError, APIError, HTTPError, TimeoutError) as exc:
            raise StoryboardGenerationUnavailable(
                "Script generation failed; saved content is unchanged. Please try again"
            ) from exc

    async def _run(self, request: ScriptAgentRequest) -> ScriptAgentResponse:
        async def turn(state: AgentSessionRun) -> ScriptAgentResponse:
            async with self._scope() as agent:
                prompt = asdict(request)
                prompt.pop("session", None)
                result = await agent.run(
                    json.dumps(prompt),
                    conversation=state.conversation,
                    deps=request,
                    usage_limits=state.limits(request_limit=4, total_tokens_limit=100000),
                    timeout=240,
                )
                usage = state.capture(result)
                return ScriptAgentResponse(
                    result.output.to_domain(),
                    PlanGeneration(
                        self._model,
                        usage.requests,
                        usage.tool_calls,
                        usage.total_tokens,
                        state.session_id,
                    ),
                )

        return (await self._sessions.run(request.session, "script", turn)).output
