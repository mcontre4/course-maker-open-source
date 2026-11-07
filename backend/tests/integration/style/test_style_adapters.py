import httpx
import pytest

from app.courses.adapters.ai.style import ElevenLabsVoices, OpenRouterStylePlanner
from app.courses.domain.generation import GenerationMode
from app.courses.ports.style import StyleUnavailable, VoiceOption

pytestmark = pytest.mark.integration


def test_catalog_paginates_and_returns_preview_and_labels(style_server):
    with style_server() as (url, calls), httpx.Client(base_url=url) as client:
        voices = ElevenLabsVoices(client, "test-key").list()
    assert [v.id for v in voices] == ["friendly", "steady"]
    assert voices[0].preview_url == "https://example.com/sample.mp3"
    assert voices[0].labels == ("language: en",)
    assert "page2" in calls[1][0]


def test_restricted_key_explicitly_falls_back_to_configured_voice(style_server):
    with style_server(voice_status=401) as (url, _), httpx.Client(base_url=url) as client:
        voices = ElevenLabsVoices(
            client, "test-key", VoiceOption("configured", "Configured")
        ).list()
    assert voices[0].id == "configured"
    assert "catalog_permission_required" in voices[0].labels


def test_provider_failure_does_not_masquerade_as_empty_catalog(style_server):
    with style_server(voice_status=500) as (url, _), httpx.Client(base_url=url) as client:
        with pytest.raises(StyleUnavailable):
            ElevenLabsVoices(client, "test-key").list()
        assert ElevenLabsVoices(client, "").list() == ()


def test_planner_sends_fast_model_context_and_real_candidates(style_server):
    with style_server() as (url, calls), httpx.Client(base_url=url) as client:
        result = OpenRouterStylePlanner(client, "test-key").resolve(
            "Explain rainbows",
            "Warm and playful",
            "Children aged 8–10",
            (VoiceOption("friendly", "Friendly"),),
            GenerationMode.FAST,
            accent="American",
            tone="Calm",
            pacing="Relaxed",
        )
    assert result.voice_id == "friendly" and result.delivery == "Warm, reassuring"
    body = calls[0][1]
    assert body["model"] == "anthropic/claude-sonnet-5.5"
    assert "service_tier" not in body
    assert body["reasoning"]["effort"] == "medium"
    assert "Children aged 8" in body["messages"][1]["content"]
    assert "friendly" in body["messages"][1]["content"]
    import json

    preferences = json.loads(body["messages"][1]["content"])
    assert preferences["accent"] == "American"
    assert preferences["tone"] == "Calm" and preferences["pacing"] == "Relaxed"
    assert "Explicit tone and pacing override inference" in body["messages"][0]["content"]


@pytest.mark.parametrize("model_status", [401, 500])
def test_planner_failures_are_explicit(style_server, model_status):
    with style_server(model_status=model_status) as (url, _), httpx.Client(base_url=url) as client:
        with pytest.raises(StyleUnavailable):
            OpenRouterStylePlanner(client, "test-key").resolve(
                "Topic", "Warm", "", (), GenerationMode.FAST
            )


def test_missing_model_key_is_explicit(style_server):
    with style_server() as (url, calls), httpx.Client(base_url=url) as client:
        with pytest.raises(StyleUnavailable):
            OpenRouterStylePlanner(client, "").resolve("Topic", "Warm", "", (), GenerationMode.FAST)
        assert not calls
