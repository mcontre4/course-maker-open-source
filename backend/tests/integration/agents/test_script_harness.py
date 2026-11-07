import json
from contextlib import asynccontextmanager
from dataclasses import asdict

import pytest
from fakes.spend import FixedBilling, InMemorySpend
from fixtures.lesson_plan import lesson_plan
from fixtures.script import script_from_board, visual_output
from fixtures.storyboard import storyboard
from fixtures.syllabus import make_planned_course
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from app.courses.adapters.ai.script import PydanticScriptAgent, ScriptOutput, validate_script
from app.courses.adapters.ai.scripted_storyboard import ScriptedStoryboardAgent
from app.courses.adapters.ai.spend import ProviderUsageTracking
from app.courses.adapters.ai.storyboard import (
    PydanticStoryboardAgent,
    StoryboardOutput,
    validate_storyboard,
)
from app.courses.domain.generation import GenerationMode
from app.courses.ports.script_agent import ScriptAgentRequest
from app.courses.ports.storyboard_agent import (
    StoryboardAgentRequest,
    StoryboardGenerationUnavailable,
    VisualStoryboardRequest,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("invalid", [None, "words", "visual_fields", "provider", "correctable"])
def test_script_schema_validation_retries_and_scope_lifecycle(invalid):
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    expected = script_from_board(storyboard(plan))
    calls, closed = [], []

    def model(messages, info):
        calls.append(messages)
        if invalid == "provider":
            raise TimeoutError("Provider timed out")
        output = json.loads(json.dumps(asdict(expected)))
        if invalid == "words":
            output["segments"][0]["narration_text"] = "Too short."
            output["segments"][1]["narration_text"] = "Too short."
        elif invalid == "visual_fields":
            output["segments"][0]["camera"] = "Push in"
        elif invalid == "correctable" and len(calls) == 1:
            output["lesson_id"] = "other"
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model), output_type=ScriptOutput, deps_type=ScriptAgentRequest, retries=1
        )
        agent.output_validator(validate_script)
        try:
            yield agent
        finally:
            closed.append(True)

    runner = PydanticScriptAgent(scope, "test-model")
    request = ScriptAgentRequest(plan, curriculum.guide, 10)
    if invalid in {"words", "visual_fields", "provider"}:
        with pytest.raises(StoryboardGenerationUnavailable):
            runner.run(request)
    else:
        response = runner.run(request)
        assert response.script == expected
        assert response.usage.requests == (2 if invalid == "correctable" else 1)
    assert closed == [True]


@pytest.mark.parametrize("failure", [None, "script", "storyboard"])
def test_two_agents_receive_separate_inputs_and_preserve_frozen_speech(failure):
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    expected = storyboard(plan)
    script = script_from_board(expected)
    calls = []

    def model(messages, info):
        prompt = next(p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart))
        supplied = json.loads(
            prompt
            if isinstance(prompt, str)
            else next(item for item in prompt if isinstance(item, str))
        )
        stage = "script" if "plan" in supplied else "storyboard"
        calls.append((stage, supplied))
        if failure == stage:
            raise TimeoutError("Provider unavailable")
        output = asdict(script) if stage == "script" else visual_output(expected)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, json.dumps(output))])

    @asynccontextmanager
    async def scripting():
        agent = Agent(FunctionModel(model), output_type=ScriptOutput, deps_type=ScriptAgentRequest)
        agent.output_validator(validate_script)
        yield agent

    @asynccontextmanager
    async def visuals():
        agent = Agent(
            FunctionModel(model), output_type=StoryboardOutput, deps_type=VisualStoryboardRequest
        )
        agent.output_validator(validate_storyboard)
        yield agent

    ledger = InMemorySpend()
    tracking = ProviderUsageTracking(ledger, FixedBilling())
    runner = ScriptedStoryboardAgent(
        PydanticScriptAgent(scripting, "test-model"),
        PydanticStoryboardAgent(visuals, "test-model"),
        tracking=tracking,
    )
    request = StoryboardAgentRequest(
        plan, curriculum.guide, 10, generation_mode=GenerationMode.PRO, visual_style_id="whiteboard"
    )
    with tracking.scope(None, plan.lesson_id, "storyboard"):
        if failure:
            with pytest.raises(StoryboardGenerationUnavailable):
                runner.run(request)
        else:
            response = runner.run(request)
            assert response.storyboard == expected
            assert response.usage.requests == 2
            assert calls[1][1]["script"] == json.loads(json.dumps(asdict(script)))
            assert calls[1][1]["visual_style_id"] == "whiteboard"
            assert "plan" not in calls[1][1]
    steps = ledger.list_steps(lesson_id=plan.lesson_id)
    assert [s.stage for s in steps] == (
        ["script"] if failure == "script" else ["script", "storyboard"]
    )
    assert all(s.finished_at is not None for s in steps)
    assert calls[0][0] == "script"
    assert calls[0][1]["generation_mode"] == "pro"
    assert len(calls) == (1 if failure == "script" else 2)
