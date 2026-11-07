import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import pytest
from fixtures.lesson_plan import lesson_plan
from fixtures.script import script_from_board, visual_output
from fixtures.storyboard import storyboard
from fixtures.syllabus import make_planned_course
from pydantic_ai import BinaryContent
from pydantic_ai.messages import ModelResponse, SystemPromptPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from app.courses.adapters.ai.storyboard import PydanticStoryboardAgent
from app.courses.adapters.ai.visual_reference import select_teaching_example
from app.courses.composition import build_storyboard_agent
from app.courses.domain.generation import GenerationMode
from app.courses.ports.storyboard_agent import (
    StoryboardAgentRequest,
    StoryboardGenerationUnavailable,
    VisualStoryboardRequest,
)

pytestmark = pytest.mark.integration


def test_production_storyboard_scope_resolves_style_for_each_request(profile_settings):
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    config = profile_settings.model_copy(update={"animator_tools_directory": str(tools)})
    runner = build_storyboard_agent(config, mode=GenerationMode.BALANCED)
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    expected = storyboard(plan)
    prompts = []

    def model(messages, info):
        prompts.append(
            "\n".join(
                part.content
                for message in messages
                for part in message.parts
                if isinstance(part, SystemPromptPart)
            )
        )
        return ModelResponse(
            usage=RequestUsage(input_tokens=100, output_tokens=100),
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(visual_output(expected)))],
        )

    async def generate():
        # Exercise the production prompt callbacks and schema with an injected offline model.
        async with runner.visuals._scope() as agent:
            with agent.override(model=FunctionModel(model)):
                for style_id in (
                    "flat-vector-science",
                    "watercolor-wash",
                    "tech-glow",
                    "whiteboard",
                    "halftone-pop",
                    "risograph",
                    "gouache-poster",
                    "soft-3d",
                    "memphis",
                    "bauhaus",
                    "swiss-grid",
                ):
                    request = VisualStoryboardRequest(
                        script_from_board(expected), curriculum.guide, visual_style_id=style_id
                    )
                    result = await agent.run(json.dumps(asdict(request)), deps=request)
                    assert result.output.to_domain(request.script) == expected
                    assert (tools / "styles" / style_id / "STYLE.md").read_text() in prompts[-1]
                    assert f"Selected visual style: {style_id}, version 1." in prompts[-1]
                    assert "Selected teaching example" in prompts[-1]
                    if style_id != "flat-vector-science":
                        assert (
                            "The selected visual style is the versioned Flat-Vector"
                            not in prompts[-1]
                        )
                        assert "# Flat-Vector Science" not in prompts[-1]

    asyncio.run(generate())
    assert len(prompts) == 11


def test_storyboard_receives_reference_pixels_and_retains_cue_development(profile_settings):

    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    config = profile_settings.model_copy(update={"animator_tools_directory": str(tools)})
    production = build_storyboard_agent(config, mode=GenerationMode.BALANCED).visuals
    _, curriculum = make_planned_course()
    expected = storyboard(lesson_plan(curriculum.chapters[0].lessons[0]))
    request = VisualStoryboardRequest(script_from_board(expected), curriculum.guide)
    images = []

    def model(messages, info):
        for message in messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart) and not isinstance(part.content, str):
                    images.extend(item for item in part.content if isinstance(item, BinaryContent))
        return ModelResponse(
            usage=RequestUsage(input_tokens=100, output_tokens=100),
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(visual_output(expected)))],
        )

    @asynccontextmanager
    async def scope():
        async with production._scope() as agent:
            with agent.override(model=FunctionModel(model)):
                yield agent

    result = PydanticStoryboardAgent(scope, "offline", tools=tools).run(request)
    example = select_teaching_example(tools, request.visual_style_id, asdict(request.script))
    assert len(images) == 1 and images[0].data == example.image.read_bytes()
    assert result.storyboard == expected
    cue = result.storyboard.scenes[0].cues[0]
    assert cue.focus and cue.relationship and cue.hold


def test_missing_selected_reference_fails_before_a_provider_request(profile_settings, tmp_path):
    config = profile_settings.model_copy(update={"animator_tools_directory": str(tmp_path)})
    runner = build_storyboard_agent(config, mode=GenerationMode.FAST)
    _, curriculum = make_planned_course()
    request = StoryboardAgentRequest(
        lesson_plan(curriculum.chapters[0].lessons[0]),
        curriculum.guide,
        10,
        visual_style_id="watercolor-wash",
    )
    with pytest.raises(StoryboardGenerationUnavailable, match="watercolor-wash v1"):
        runner.run(request)


def test_missing_teaching_source_fails_before_scripting(profile_settings, tmp_path):
    style = tmp_path / "styles/flat-vector-science"
    style.mkdir(parents=True)
    (style / "STYLE.md").write_text("Selected drawing medium")
    catalog = tmp_path / "teaching-examples"
    catalog.mkdir()
    (catalog / "manifest.json").write_text(
        json.dumps(
            {
                "default": "mechanism",
                "examples": [{"id": "mechanism", "source": "missing.js"}],
            }
        )
    )
    config = profile_settings.model_copy(update={"animator_tools_directory": str(tmp_path)})
    runner = build_storyboard_agent(config, mode=GenerationMode.FAST)
    _, curriculum = make_planned_course()
    request = StoryboardAgentRequest(
        lesson_plan(curriculum.chapters[0].lessons[0]),
        curriculum.guide,
        10,
    )
    # Production would make an HTTP request with these fake credentials if preflight failed.
    with pytest.raises(StoryboardGenerationUnavailable, match="teaching reference"):
        runner.run(request)
