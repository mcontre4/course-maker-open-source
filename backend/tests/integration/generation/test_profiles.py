import asyncio
import json

import pytest
from httpx2 import AsyncClient, MockTransport, Response
from openai import AsyncOpenAI
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.courses.adapters.ai.scripted_storyboard import ScriptedStoryboardAgent
from app.courses.composition import build_lesson_agent, build_storyboard_agent, build_syllabus_agent
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animator_model import AnimatorModel

pytestmark = pytest.mark.integration

EXPECTED = (
    (GenerationMode.FAST, "anthropic/claude-sonnet-5.5", "medium"),
    (GenerationMode.BALANCED, "anthropic/claude-opus-5.5", "medium"),
    (GenerationMode.PRO, "anthropic/claude-opus-5.5", "max"),
)


@pytest.mark.parametrize(
    "build", (build_syllabus_agent, build_lesson_agent, build_storyboard_agent)
)
@pytest.mark.parametrize("override", (None, *AnimatorModel))
def test_production_composition_configures_every_model_and_reasoning_level(
    build, profile_settings, override
):
    routed = build(profile_settings, model_override=override)

    async def inspect():
        for mode, model, effort in EXPECTED:
            selected = override.value if override else model
            model = selected.removesuffix(":fast")
            pipeline = routed.agents[mode]
            runners = (
                (pipeline.scripting, pipeline.visuals)
                if isinstance(pipeline, ScriptedStoryboardAgent)
                else (pipeline,)
            )
            for runner in runners:
                # Enter the real adapter's request scope, without running an LLM or search.
                async with runner._scope() as agent:
                    assert agent.model.model_name == model
                    assert agent.model_settings["openai_reasoning_effort"] == effort
                    assert agent.model_settings["openai_store"] is False
                    requests = []

                    def respond(request):
                        requests.append(json.loads(request.content))
                        return Response(
                            200,
                            json={
                                "id": "resp_offline",
                                "object": "response",
                                "created_at": 1,
                                "model": model,
                                "status": "completed",
                                "output": [
                                    {
                                        "type": "message",
                                        "id": "msg_offline",
                                        "role": "assistant",
                                        "content": [
                                            {
                                                "type": "output_text",
                                                "text": "Done",
                                                "annotations": [],
                                            }
                                        ],
                                    }
                                ],
                                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                            },
                        )

                    # Exercise production settings through an injected HTTP boundary.
                    async with AsyncClient(transport=MockTransport(respond)) as http:
                        async with AsyncOpenAI(
                            api_key="offline",
                            base_url="https://openrouter.ai/api/v1",
                            http_client=http,
                        ) as client:
                            transport_model = OpenAIResponsesModel(
                                agent.model.model_name,
                                provider=OpenRouterProvider(openai_client=client),
                            )
                            await transport_model.request(
                                [ModelRequest(parts=[UserPromptPart("Explain atoms")])],
                                agent.model_settings,
                                ModelRequestParameters(),
                            )
                    assert requests[0]["model"] == model
                    assert requests[0].get("service_tier") == (
                        ("fast" if selected.startswith("anthropic/") else "priority")
                        if selected.endswith(":fast")
                        else None
                    )
                    assert requests[0]["reasoning"]["effort"] == effort

    asyncio.run(inspect())


@pytest.mark.parametrize("mode, default_model, effort", EXPECTED)
def test_direct_profiles_and_overrides_share_author_and_reviewer_model(
    profile_settings, mode, default_model, effort
):
    from app.courses.composition import build_animator
    from app.courses.ports.animator_model import AnimatorModel

    routed = build_animator(profile_settings)
    for override in (None, *AnimatorModel):
        production = (
            routed.animators[mode] if override is None else routed.model_animators[mode, override]
        )._production
        expected = override.value if override else default_model
        assert production._animator._llm.model == expected
        assert production._animator._llm.effort == effort
        assert production._delivery._arguments[0] == "direct-review-v1"
        assert production._delivery._arguments[1] == expected
        assert production._delivery._arguments[2] == effort
        assert production._element_agent._llm.model == expected
        assert production._element_agent._llm.effort == effort


@pytest.mark.parametrize("mode", tuple(GenerationMode))
@pytest.mark.parametrize("override", (None, *AnimatorModel))
def test_guide_and_summarizer_share_general_override(profile_settings, mode, override):
    from app.courses.adapters.ai.generation import generation_profile
    from app.courses.adapters.ai.model_options import model_options
    from app.courses.composition import build_guide_agent

    guide = build_guide_agent(profile_settings, model_override=override)
    expected = model_options(generation_profile(mode, override).model)

    async def inspect():
        async with guide._scope(mode) as agents:
            for agent in agents:
                assert agent.model.model_name == expected["model"]
                assert agent.model_settings["openai_reasoning_effort"] == (
                    "max" if mode is GenerationMode.PRO else "medium"
                )
                assert agent.model_settings["extra_body"] == {
                    k: v for k, v in expected.items() if k != "model"
                }

    asyncio.run(inspect())
