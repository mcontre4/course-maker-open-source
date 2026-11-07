import json
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from fixtures.lesson_plan import lesson_plan
from fixtures.script import script_from_board, visual_output
from fixtures.storyboard import storyboard
from fixtures.syllabus import make_planned_course
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.courses.adapters.ai.storyboard import (
    PydanticStoryboardAgent,
    StoryboardOutput,
    validate_storyboard,
)
from app.courses.ports.storyboard_agent import (
    StoryboardGenerationUnavailable,
    VisualStoryboardRequest,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "invalid", [None, "anchor", "coverage", "cue_order", "timestamp", "provider", "rewrite"]
)
def test_real_agent_validates_output_retries_and_closes_scope(invalid):
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    expected = storyboard(plan)
    if invalid == "cue_order":
        scene = expected.scenes[0]
        scene = replace(
            scene,
            narration_text=scene.narration_text + "The result is ready to compare.",
            cues=(
                *scene.cues,
                replace(
                    scene.cues[0],
                    id="result",
                    anchor_text="The result is ready to compare",
                    action="Hold the result beside the starting value",
                ),
            ),
        )
        expected = replace(expected, scenes=(scene, *expected.scenes[1:]))
    request = VisualStoryboardRequest(script_from_board(expected), curriculum.guide)
    calls, closed = [], []

    def model(messages, info):
        calls.append(messages)
        if invalid == "provider":
            raise TimeoutError("Provider timed out")
        output = json.loads(json.dumps(visual_output(expected)))
        if invalid == "anchor":
            output["scenes"][0]["cues"][0]["anchor_text"] = "absent"
        elif invalid == "coverage" and len(calls) == 1:
            output["scenes"][0]["scene_id"] = "unknown"
        elif invalid == "cue_order" and len(calls) == 1:
            output["scenes"][0]["cues"].reverse()
        elif invalid == "timestamp":
            output["scenes"][0]["start_ms"] = 1000
        elif invalid == "rewrite":
            output["scenes"][0]["narration_text"] = "The storyboard rewrote the script."
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model),
            output_type=StoryboardOutput,
            deps_type=VisualStoryboardRequest,
            retries=1,
        )
        agent.output_validator(validate_storyboard)
        try:
            yield agent
        finally:
            closed.append(True)

    runner = PydanticStoryboardAgent(scope, "test-model")
    if invalid in ("anchor", "timestamp", "provider", "rewrite"):
        with pytest.raises(StoryboardGenerationUnavailable):
            runner.run(request)
    else:
        result = runner.run(request)
        assert result.storyboard == expected
        assert result.usage.requests == (2 if invalid in ("coverage", "cue_order") else 1)
        assert result.usage.tool_calls == 0
    assert closed == [True]
