"""Two isolated provider stages behind the existing generation boundary."""

from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path

from app.courses.adapters.ai.spend import ProviderUsageTracking
from app.courses.adapters.ai.visual_reference import storyboard_style_reference
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.ports.script_agent import ScriptAgent, ScriptAgentRequest
from app.courses.ports.storyboard_agent import (
    StoryboardAgentRequest,
    StoryboardAgentResponse,
    VisualStoryboardAgent,
    VisualStoryboardRequest,
)


@dataclass(frozen=True)
class ScriptedStoryboardAgent:
    scripting: ScriptAgent
    visuals: VisualStoryboardAgent
    tracking: ProviderUsageTracking | None = None
    tools: Path | None = None

    def run(self, request: StoryboardAgentRequest) -> StoryboardAgentResponse:
        if self.tools is not None:
            storyboard_style_reference(
                self.tools,
                request.visual_style_id,
                request.visual_style_version,
            )
        with self.tracking.worker("script") if self.tracking else nullcontext():
            scripted = self.scripting.run(
                ScriptAgentRequest(
                    request.plan,
                    request.guide,
                    request.target_video_minutes,
                    request.generation_mode,
                    session=replace(request.session, session_id=request.script_session_id)
                    if request.session
                    else None,
                    message=request.message,
                )
            )
        scripted.script.validate_plan(request.plan, request.target_video_minutes)
        with self.tracking.worker("storyboard") if self.tracking else nullcontext():
            directed = self.visuals.run(
                VisualStoryboardRequest(
                    scripted.script,
                    request.guide,
                    request.visual_style,
                    request.visual_style_id,
                    request.visual_style_version,
                    session=request.session,
                    message=request.message,
                )
            )
        directed.storyboard.validate_script(scripted.script)
        first, second = scripted.usage, directed.usage
        return StoryboardAgentResponse(
            directed.storyboard,
            PlanGeneration(
                first.model if first.model == second.model else f"{first.model} / {second.model}",
                first.requests + second.requests,
                first.tool_calls + second.tool_calls,
                first.total_tokens + second.total_tokens,
                second.session_id,
            ),
            scripted.usage.session_id,
        )
