import pytest

from app.courses.domain.generation import GenerationMode
from app.courses.ports.animator_model import AnimatorModel

pytestmark = pytest.mark.integration

STAGES = (
    "syllabus",
    "lesson",
    "storyboard",
    "animation",
    "standalone-plan",
    "standalone-storyboard",
    "standalone-animation",
)


def calls(agent):
    return getattr(agent, "requests", getattr(agent, "calls", []))


@pytest.mark.parametrize("generation_http", STAGES, indirect=True)
@pytest.mark.parametrize("mode", tuple(GenerationMode))
def test_http_mode_reaches_only_the_selected_ai_boundary(generation_http, mode):
    client, path, body, agents, _, model_agents = generation_http
    response = client.post(path, json={**body, "generationMode": mode.value})
    assert response.status_code == 200, response.text
    assert len(calls(agents[mode])) == 1
    assert calls(agents[mode])[0].generation_mode == mode
    assert all(not calls(agent) for choice, agent in agents.items() if choice != mode)


@pytest.mark.parametrize("generation_http", STAGES, indirect=True)
def test_omitted_mode_defaults_to_balanced(generation_http):
    client, path, body, agents, _, model_agents = generation_http
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    assert len(calls(agents[GenerationMode.BALANCED])) == 1


@pytest.mark.parametrize("generation_http", STAGES, indirect=True)
@pytest.mark.parametrize("mode", ["ultra", "openai/gpt-6.1-sol", None])
def test_invalid_modes_never_call_an_ai_boundary(generation_http, mode):
    client, path, body, agents, _, model_agents = generation_http
    assert client.post(path, json={**body, "generationMode": mode}).status_code == 422
    assert all(not calls(agent) for agent in [*agents.values(), *model_agents.values()])


@pytest.mark.parametrize("generation_http", ["animation", "standalone-animation"], indirect=True)
@pytest.mark.parametrize("model", [None, *AnimatorModel])
def test_http_animator_override_is_validated_and_forwarded(generation_http, model):
    client, path, body, agents, _, model_agents = generation_http
    response = client.post(path, json={**body, "animatorModel": model})
    assert response.status_code == 200, response.text
    selected = (
        agents[GenerationMode.BALANCED]
        if model is None
        else model_agents[GenerationMode.BALANCED, model]
    )
    assert calls(selected)[0].animator_model == model
    assert all(
        not calls(agent)
        for agent in [*agents.values(), *model_agents.values()]
        if agent is not selected
    )


@pytest.mark.parametrize("generation_http", ["animation", "standalone-animation"], indirect=True)
@pytest.mark.parametrize("enabled", [False, True])
def test_http_element_preparation_flag_is_validated_and_forwarded(generation_http, enabled):
    client, path, body, agents, _, _ = generation_http
    invalid = client.post(path, json={**body, "prepareElements": "true"})
    assert invalid.status_code == 422
    assert not calls(agents[GenerationMode.BALANCED])
    response = client.post(path, json={**body, "prepareElements": enabled})
    assert response.status_code == 200, response.text
    assert calls(agents[GenerationMode.BALANCED])[0].prepare_elements is enabled


@pytest.mark.parametrize("generation_http", ["animation", "standalone-animation"], indirect=True)
@pytest.mark.parametrize("model", ["arbitrary/model", "", 42])
def test_unknown_animator_models_never_call_provider(generation_http, model):
    client, path, body, agents, _, model_agents = generation_http
    assert client.post(path, json={**body, "animatorModel": model}).status_code == 422
    assert all(not calls(agent) for agent in [*agents.values(), *model_agents.values()])
