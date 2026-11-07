import pytest

from app.courses.domain.generation import GenerationMode
from app.courses.ports.animator_model import AnimatorModel

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("video_http", ["course", "standalone"], indirect=True)
@pytest.mark.parametrize("model", [None, *AnimatorModel])
def test_video_endpoint_forwards_animator_choice_to_use_case(video_http, model):
    client, path, body, service = video_http
    response = client.post(path, json={**body, "animatorModel": model, "generationMode": "fast"})
    assert response.status_code == 200, response.text
    assert len(service.requests) == 1
    assert service.requests[0].animator_model == model
    assert service.requests[0].generation_mode == GenerationMode.FAST


@pytest.mark.parametrize("video_http", ["course", "standalone"], indirect=True)
def test_video_endpoint_keeps_mode_default_when_animator_choice_is_omitted(video_http):
    client, path, body, service = video_http
    assert client.post(path, json=body).status_code == 200
    assert service.requests[0].animation_backend.value == "direct"
    assert service.requests[0].animator_model is None
    assert service.requests[0].generation_mode == GenerationMode.BALANCED


@pytest.mark.parametrize("video_http", ["course", "standalone"], indirect=True)
@pytest.mark.parametrize("model", ["arbitrary/model", "", 42])
def test_video_endpoint_rejects_unknown_animator_choice_before_generation(video_http, model):
    client, path, body, service = video_http
    assert client.post(path, json={**body, "animatorModel": model}).status_code == 422
    assert not service.requests


@pytest.mark.parametrize("video_http", ["course", "standalone"], indirect=True)
@pytest.mark.parametrize("backend", ["direct"])
def test_video_endpoint_forwards_one_engine_choice_for_both_agents(video_http, backend):
    client, path, body, service = video_http
    response = client.post(
        path,
        json={
            **body,
            "animationBackend": backend,
            "animatorModel": AnimatorModel.LUNA.value,
            "generationMode": "fast",
        },
    )
    assert response.status_code == 200, response.text
    assert service.requests[0].animation_backend.value == backend
    assert service.requests[0].animator_model == AnimatorModel.LUNA


@pytest.mark.parametrize("video_http", ["course", "standalone"], indirect=True)
@pytest.mark.parametrize("backend", ["codex", "unknown", "", None])
def test_unknown_engine_is_rejected_before_generation(video_http, backend):
    client, path, body, service = video_http
    assert client.post(path, json={**body, "animationBackend": backend}).status_code == 422
    assert not service.requests
