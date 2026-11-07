import json
from typing import Annotated, Any

import httpx
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.courses.adapters.ai.direct_animation import DirectAnimationCall
from app.courses.adapters.ai.scripted_storyboard import ScriptedStoryboardAgent
from app.courses.adapters.http import lessons, standalone, storyboards, syllabus, video
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animator_model import AnimatorModel

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "dependency",
    (
        lessons.get_lesson_generator,
        storyboards.get_storyboard_generator,
        syllabus.get_generator,
        standalone.get_plan,
        standalone.get_storyboard,
    ),
)
def test_header_override_is_validated_and_isolated_per_request(
    composed_generation_http, dependency
):
    app, fallback = composed_generation_http

    @app.get("/probe")
    async def probe(service: Annotated[Any, Depends(dependency)]):
        if service._agent is fallback:
            return {"model": "automatic"}
        selected = service._agent.agents[GenerationMode.BALANCED]
        if isinstance(selected, ScriptedStoryboardAgent):
            async with selected.scripting._scope() as scripting:
                assert scripting.model.model_name == AnimatorModel.OPUS.value
            selected = selected.visuals
        async with selected._scope() as agent:
            return {"model": agent.model.model_name, "options": agent.model_settings["extra_body"]}

    with TestClient(app) as client:
        assert client.get("/probe").json() == {"model": "automatic"}
        result = client.get("/probe", headers={"X-Generation-Model": AnimatorModel.OPUS_FAST.value})
        assert result.status_code == 200
        assert result.json() == {
            "model": AnimatorModel.OPUS.value,
            "options": {"service_tier": "fast"},
        }
        assert client.get("/probe").json() == {"model": "automatic"}
        assert client.get("/probe", headers={"X-Generation-Model": "arbitrary"}).status_code == 422


@pytest.mark.parametrize(
    "dependency", (video.get_course_video, video.get_standalone_video, video.get_automatic_lesson)
)
def test_combined_video_resolves_with_general_override(composed_generation_http, dependency):
    app, _ = composed_generation_http

    @app.get("/probe")
    def probe(service: Annotated[Any, Depends(dependency)]):
        return {"service": type(service).__name__}

    with TestClient(app) as client:
        result = client.get("/probe", headers={"X-Generation-Model": AnimatorModel.OPUS_FAST.value})
        assert result.status_code == 200
        assert result.json()["service"].startswith("Generate")


@pytest.mark.parametrize("model", tuple(AnimatorModel))
def test_direct_model_and_tier_mapping(model):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "Done"}}]}
        )

    call = DirectAnimationCall(
        lambda: httpx.Client(transport=httpx.MockTransport(respond)),
        "offline",
        model.value,
        "medium",
    )
    assert (
        call.complete("Instructions", [{"type": "text", "text": "Explain"}], "animation") == "Done"
    )
    assert requests[0]["model"] == model.value.removesuffix(":fast")
    tier = "fast" if model == AnimatorModel.OPUS_FAST else "priority"
    assert requests[0].get("service_tier") == (tier if model.value.endswith(":fast") else None)


@pytest.mark.parametrize("model", tuple(AnimatorModel))
def test_style_override_reuses_client_without_changing_default_planner(model):
    from app.courses.adapters.ai.style import OpenRouterStylePlanner
    from app.courses.ports.style import StyleUnavailable

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(503)

    with httpx.Client(
        base_url="https://openrouter.ai", transport=httpx.MockTransport(respond)
    ) as client:
        planner = OpenRouterStylePlanner(client, "offline")
        selected = planner.for_model(model)
        with pytest.raises(StyleUnavailable):
            selected.resolve("Topic", "Style", "Audience", (), GenerationMode.PRO)
        with pytest.raises(StyleUnavailable):
            planner.resolve("Topic", "Style", "Audience", (), GenerationMode.PRO)
    assert requests[0]["model"] == model.value.removesuffix(":fast")
    tier = "fast" if model == AnimatorModel.OPUS_FAST else "priority"
    assert requests[0].get("service_tier") == (tier if model.value.endswith(":fast") else None)
    assert requests[1]["model"] == AnimatorModel.OPUS.value
    assert requests[0]["reasoning"]["effort"] == "max"
    assert requests[1]["reasoning"]["effort"] == "max"
    assert "service_tier" not in requests[1]


def test_automatic_override_selects_both_agents_and_leaves_defaults_isolated(
    composed_generation_http,
):
    app, fallback = composed_generation_http

    @app.get("/automatic-probe")
    async def probe(service: Annotated[Any, Depends(video.get_automatic_lesson)]):
        agents = (service._planner._agent, service._video._storyboard._agent)
        models = []
        for selected in agents:
            if selected is fallback:
                models.append("automatic")
            else:
                runner = selected.agents[GenerationMode.BALANCED]
                if isinstance(runner, ScriptedStoryboardAgent):
                    async with runner.scripting._scope() as scripting:
                        assert scripting.model.model_name == AnimatorModel.OPUS.value
                    runner = runner.visuals
                async with runner._scope() as agent:
                    models.append(agent.model.model_name)
        return models

    with TestClient(app) as client:
        assert client.get("/automatic-probe").json() == ["automatic", "automatic"]
        result = client.get(
            "/automatic-probe", headers={"X-Generation-Model": AnimatorModel.OPUS_FAST.value}
        )
        assert result.status_code == 200
        assert result.json() == [AnimatorModel.OPUS.value, AnimatorModel.OPUS.value]
        assert client.get("/automatic-probe").json() == ["automatic", "automatic"]
