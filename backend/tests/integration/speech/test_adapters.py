import io
import wave

import httpx
import pytest
from fixtures.elevenlabs import elevenlabs_server

from app.courses.adapters.ai.elevenlabs import ElevenLabsSpeech
from app.courses.adapters.storage.speech import LocalSpeechArtifacts
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.speech import SpeechArtifactUnavailable, SpeechUnavailable

pytestmark = pytest.mark.integration


def test_elevenlabs_http_contract_and_measured_wav():
    with elevenlabs_server() as (url, requests), httpx.Client(base_url=url) as client:
        result = ElevenLabsSpeech(client, "test-secret").synthesize(
            " Hello, world! ", SpeechSettings("voice-id")
        )
    path, key, body = requests[0]
    assert path == "/v1/text-to-dialogue/with-timestamps?output_format=pcm_24000"
    assert key == "test-secret"
    assert body["model_id"] == "eleven_v4"
    assert body["inputs"][0]["text"] == " Hello, world! "
    assert body["settings"]["stability"] == 0.5
    assert "model_id" not in body["settings"]
    assert "".join(c.text for c in result.measured.characters) == body["inputs"][0]["text"]
    with wave.open(io.BytesIO(result.audio_wav)) as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24000
        assert audio.getnframes() / audio.getframerate() == result.measured.duration_sec
    assert result.measured.request_id == "local-provider-request"


@pytest.mark.parametrize("invalid", ["missing", "base64", "length", "timing", "audio"])
def test_rejects_invalid_provider_responses(invalid):
    with elevenlabs_server(invalid=invalid) as (url, _), httpx.Client(base_url=url) as client:
        with pytest.raises(SpeechUnavailable, match="unusable"):
            ElevenLabsSpeech(client, "test-secret").synthesize("Hello", SpeechSettings("voice"))


@pytest.mark.parametrize("status", [401, 422, 429, 500])
def test_provider_errors_are_sanitized(status):
    with elevenlabs_server(status=status) as (url, calls), httpx.Client(base_url=url) as client:
        with pytest.raises(SpeechUnavailable) as error:
            delays = []
            ElevenLabsSpeech(client, "private-key", delays.append).synthesize(
                "Private lesson narration", SpeechSettings("voice")
            )
    assert str(status) in str(error.value)
    assert "private-key" not in str(error.value)
    assert "Private lesson" not in str(error.value)
    assert len(calls) == (3 if status == 429 else 1)
    assert delays == ([0.5, 1.0] if status == 429 else [])


def test_private_local_storage_is_atomic_immutable_and_survives_new_instances(tmp_path):
    storage = LocalSpeechArtifacts(tmp_path)
    assert storage.read("audio/missing.wav") is None
    storage.write("audio/s01.wav", b"audio", "audio/wav")
    storage.write("audio/s01.wav", b"audio", "audio/wav")
    assert LocalSpeechArtifacts(tmp_path).read("audio/s01.wav") == b"audio"
    assert (tmp_path / "audio/s01.wav").stat().st_mode & 0o077 == 0
    with pytest.raises(SpeechArtifactUnavailable, match="already exists"):
        storage.write("audio/s01.wav", b"changed", "audio/wav")
    assert storage.read("audio/s01.wav") == b"audio"


@pytest.mark.parametrize("key", ["../outside", "/tmp/outside", "audio/../../outside", ""])
def test_private_storage_rejects_unsafe_keys(tmp_path, key):
    with pytest.raises(SpeechArtifactUnavailable):
        LocalSpeechArtifacts(tmp_path).write(key, b"private", "audio/wav")


def test_private_storage_rejects_symlink_escape(tmp_path):
    root = tmp_path / "private"
    storage = LocalSpeechArtifacts(root)
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SpeechArtifactUnavailable):
        storage.write("escape/outside", b"private", "audio/wav")


def test_terminal_punctuation_is_bounded_by_measured_audio():
    with elevenlabs_server(invalid="punctuation") as (url, _), httpx.Client(base_url=url) as client:
        result = ElevenLabsSpeech(client, "test").synthesize("Hello.", SpeechSettings("voice"))
    assert result.measured.characters[-1].end_sec == result.measured.duration_sec
    assert result.measured.characters[-2].end_sec == 0.05


def test_long_scene_chunks_preserve_text_and_use_sample_accurate_offsets():
    text = "Look at the name score. " + "A name refers to a value. " * 104
    with elevenlabs_server() as (url, calls), httpx.Client(base_url=url) as client:
        result = ElevenLabsSpeech(client, "test").synthesize(text, SpeechSettings("voice"))
    assert len(calls) == 2
    assert all(len(call[2]["inputs"][0]["text"]) <= 2000 for call in calls)
    assert "".join(call[2]["inputs"][0]["text"] for call in calls) == text
    assert "".join(c.text for c in result.measured.characters) == text
    assert result.measured.characters[-1].end_sec == result.measured.duration_sec
    with wave.open(io.BytesIO(result.audio_wav)) as audio:
        assert audio.getnframes() / 24000 == len(text) / 100


def test_fractional_sample_duration_does_not_fail_after_timestamp_rounding():
    duration = 48001 / 24000
    with (
        elevenlabs_server(chunk_durations=[duration]) as (url, _),
        httpx.Client(base_url=url) as client,
    ):
        result = ElevenLabsSpeech(client, "test").synthesize("Hello.", SpeechSettings("voice"))
    assert result.measured.duration_sec == duration
    assert result.measured.characters[-1].end_sec == duration
    with wave.open(io.BytesIO(result.audio_wav)) as audio:
        assert audio.getnframes() == 48001


def test_quota_failure_has_actionable_feedback_without_echoing_provider_content():
    failure = {"detail": {"code": "quota_exceeded", "message": "private-key private narration"}}
    with (
        elevenlabs_server(status=401, error_body=failure) as (url, calls),
        httpx.Client(base_url=url) as client,
    ):
        with pytest.raises(SpeechUnavailable, match="credits are exhausted") as error:
            ElevenLabsSpeech(client, "private-key").synthesize(
                "Private narration", SpeechSettings("voice")
            )
    assert "saved script is unchanged" in str(error.value)
    assert "private-key" not in str(error.value)
    assert "private narration" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "delivery",
    ["", "Warm and curious", "Keep the pace brisk But easy to follow"],
)
@pytest.mark.parametrize("repetitions", [1, 100])
def test_delivery_instructions_never_enter_spoken_text(delivery, repetitions):
    narration = "Sunlight contains many colors. " * repetitions
    with (
        elevenlabs_server() as (url, calls),
        httpx.Client(base_url=url) as client,
    ):
        result = ElevenLabsSpeech(client, "test-key").synthesize(
            narration, SpeechSettings("friendly", delivery=delivery)
        )
    # Check every chunk at the HTTP boundary, not just the cleaned transcript:
    # removing instruction characters from alignment cannot remove spoken audio.
    assert "".join(call[2]["inputs"][0]["text"] for call in calls) == narration
    assert all("delivery" not in call[2]["settings"] for call in calls)
    assert "".join(c.text for c in result.measured.characters) == narration
    assert result.measured.characters[0].start_sec == 0
    assert result.measured.duration_sec == pytest.approx(len(narration) / 100)
    assert result.audio_wav.startswith(b"RIFF")
