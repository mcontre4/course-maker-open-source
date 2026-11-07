import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from pathlib import Path

from httpx import HTTPError
from openai import APIError
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, BinaryContent, ModelRetry, RunContext
from pydantic_ai.exceptions import AgentRunError

from app.courses.adapters.ai.agent_sessions import AgentSessionRun, PersistentAgentSessions
from app.courses.adapters.ai.visual_reference import select_teaching_example
from app.courses.domain.errors import CourseError
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.script import LessonScript
from app.courses.domain.storyboard import SpeechCue, Storyboard, StoryboardScene
from app.courses.ports.storyboard_agent import (
    StoryboardAgentResponse,
    StoryboardGenerationUnavailable,
    VisualStoryboardRequest,
)

logger = logging.getLogger(__name__)


class StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CueOutput(StructuredOutput):
    id: str
    anchor_text: str
    action: str
    focus: str = Field(min_length=1, max_length=500)
    relationship: str = Field(min_length=1, max_length=500)
    hold: str = Field(min_length=1, max_length=500)


class SceneOutput(StructuredOutput):
    scene_id: str
    visual_brief: str
    cues: list[CueOutput]
    transition: str
    on_screen_text: list[str]
    accessibility_notes: list[str]
    object_ids: list[str]
    opening_composition: str
    closing_composition: str
    camera: str
    continuity_from_previous: str


class StoryboardOutput(StructuredOutput):
    scenes: list[SceneOutput]

    def to_domain(self, script: LessonScript) -> Storyboard:
        if tuple(s.scene_id for s in self.scenes) != tuple(s.scene_id for s in script.segments):
            raise CourseError("Return visual direction for every frozen script segment in order")
        return Storyboard(
            script.lesson_id,
            script.objectives,
            script.target_video_minutes,
            tuple(
                StoryboardScene(
                    s.scene_id,
                    frozen.teaching_beat_index,
                    frozen.learning_purpose,
                    frozen.narration_text,
                    s.visual_brief,
                    tuple(
                        SpeechCue(c.id, c.anchor_text, c.action, c.focus, c.relationship, c.hold)
                        for c in s.cues
                    ),
                    frozen.target_duration_sec,
                    s.transition,
                    tuple(s.on_screen_text),
                    frozen.equations,
                    tuple(s.accessibility_notes),
                    tuple(s.object_ids),
                    s.opening_composition,
                    s.closing_composition,
                    s.camera,
                    s.continuity_from_previous,
                )
                for s, frozen in zip(self.scenes, script.segments, strict=True)
            ),
        )


def validate_storyboard(
    ctx: RunContext[VisualStoryboardRequest], output: StoryboardOutput
) -> StoryboardOutput:
    try:
        board = output.to_domain(ctx.deps.script)
    except CourseError as exc:
        raise ModelRetry(str(exc)) from exc
    for scene in board.scenes:
        positions = [scene.narration_text.index(cue.anchor_text) for cue in scene.cues]
        if positions != sorted(positions):
            raise ModelRetry(f"Order cues by their spoken anchors in scene {scene.scene_id}")
    return output


class PydanticStoryboardAgent:
    def __init__(
        self,
        scope: Callable[
            [], AbstractAsyncContextManager[Agent[VisualStoryboardRequest, StoryboardOutput]]
        ],
        model: str,
        sessions: PersistentAgentSessions | None = None,
        tools: Path | None = None,
    ) -> None:
        self._scope, self._model = scope, model
        self._sessions = sessions or PersistentAgentSessions()
        self._tools = tools

    def run(self, request: VisualStoryboardRequest) -> StoryboardAgentResponse:
        try:
            return asyncio.run(self._run(request))
        except (AgentRunError, APIError, HTTPError, TimeoutError) as exc:
            logger.warning("Storyboard provider failure: %s", type(exc).__name__)
            raise StoryboardGenerationUnavailable(
                "Storyboard generation failed; saved content is unchanged. Please try again"
            ) from exc

    async def _run(self, request: VisualStoryboardRequest) -> StoryboardAgentResponse:
        async def turn(state: AgentSessionRun) -> StoryboardAgentResponse:
            async with self._scope() as agent:
                prompt = asdict(request)
                prompt.pop("session", None)
                content: list[str | BinaryContent] = [json.dumps(prompt)]
                if self._tools is not None:
                    example = select_teaching_example(
                        self._tools, request.visual_style_id, asdict(request.script)
                    )
                    if example is not None:
                        content.extend(
                            [
                                "Selected teaching example frames: " + example.id,
                                BinaryContent(
                                    data=example.image.read_bytes(), media_type="image/png"
                                ),
                            ]
                        )
                result = await agent.run(
                    content,
                    conversation=state.conversation,
                    deps=request,
                    usage_limits=state.limits(request_limit=4, total_tokens_limit=100000),
                    timeout=240,
                )
                usage = state.capture(result)
                return StoryboardAgentResponse(
                    result.output.to_domain(request.script),
                    PlanGeneration(
                        self._model,
                        usage.requests,
                        usage.tool_calls,
                        usage.total_tokens,
                        state.session_id,
                    ),
                )

        return (await self._sessions.run(request.session, "storyboard", turn)).output
