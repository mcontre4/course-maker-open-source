import base64
import binascii
import io
import wave
from collections.abc import Callable
from dataclasses import asdict
from time import sleep

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.courses.domain.speech import AlignmentError, MeasuredSpeech, SpeechSettings, TimedText
from app.courses.ports.speech import SpeechUnavailable, SynthesizedSpeech


class CharacterAlignment(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    characters: list[str]
    character_start_times_seconds: list[float]
    character_end_times_seconds: list[float]


class SpeechPayload(BaseModel):
    audio_base64: str
    alignment: CharacterAlignment


class ElevenLabsSpeech:
    """Client ownership, timeout and credentials are supplied by the composition root."""

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        wait: Callable[[float], None] = sleep,
    ) -> None:
        self._client, self._api_key, self._wait = client, api_key, wait

    def synthesize(self, text: str, settings: SpeechSettings) -> SynthesizedSpeech:
        # Keep v4 dialogue requests <= 2,000 characters, preserving every character.
        remaining = text
        chunks = []
        while remaining:
            end = min(2000, len(remaining))
            if end < len(remaining):
                boundary = remaining.rfind(" ", 0, end)
                if boundary >= 1000:
                    end = boundary + 1
            chunks.append(remaining[:end])
            remaining = remaining[end:]
        if not chunks or len(text) > 10000:
            raise SpeechUnavailable("Speech scenes need 1–10,000 characters")
        pcm_parts = []
        characters: list[TimedText] = []
        request_ids = []
        sample_count = 0
        for chunk in chunks:
            result = self._synthesize_chunk(chunk, settings)
            offset = sample_count / settings.sample_rate
            pcm_parts.append(result.measured.pcm)
            characters.extend(
                TimedText(c.text, round(c.start_sec + offset, 9), round(c.end_sec + offset, 9))
                for c in result.measured.characters
            )
            sample_count += len(result.measured.pcm) // 2
            if result.measured.request_id:
                request_ids.append(result.measured.request_id)
        measured = MeasuredSpeech(
            b"".join(pcm_parts),
            settings.sample_rate,
            tuple(
                TimedText(
                    c.text,
                    min(c.start_sec, sample_count / settings.sample_rate),
                    min(c.end_sec, sample_count / settings.sample_rate),
                )
                for c in characters
            ),
            ",".join(request_ids) or None,
        )
        output = io.BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(settings.sample_rate)
            audio.writeframes(measured.pcm)
        return SynthesizedSpeech(measured, output.getvalue())

    def _synthesize_chunk(self, text: str, settings: SpeechSettings) -> SynthesizedSpeech:
        if not self._api_key:
            raise SpeechUnavailable("Configure COURSE_MAKER_ELEVENLABS_API_KEY")
        # Delivery is planning metadata, not speech. Free-form bracketed directions
        # can be read aloud; trimming their alignment afterward cannot fix the audio.
        voice = asdict(settings)
        for key in ("voice_id", "model_id", "sample_rate", "delivery"):
            voice.pop(key)
        try:
            for attempt in range(3):
                response = self._client.post(
                    "/v1/text-to-dialogue/with-timestamps",
                    params={"output_format": "pcm_24000"},
                    headers={"xi-api-key": self._api_key},
                    json={
                        "inputs": [{"text": text, "voice_id": settings.voice_id}],
                        "model_id": settings.model_id,
                        "settings": voice,
                    },
                )
                if response.status_code != 429 or attempt == 2:
                    break
                self._wait(0.5 * 2**attempt)
            response.raise_for_status()
            payload = SpeechPayload.model_validate_json(response.content)
            alignment = payload.alignment
            if "".join(alignment.characters) != text:
                raise AlignmentError("Provider changed or truncated the original transcript")
            pcm = base64.b64decode(payload.audio_base64, validate=True)
            duration = len(pcm) / (2 * settings.sample_rate)
            # V4 may extend nonspoken terminal punctuation/whitespace past the PCM.
            # Bound those spans by the measured end; never repair speech characters.
            characters = tuple(
                TimedText(character, min(start, duration), min(end, duration))
                if (character.isspace() or character in ".,!?;:…\"'“”‘’")
                and max(start, end) <= duration + 0.25
                else TimedText(character, start, end)
                for character, start, end in zip(
                    alignment.characters,
                    alignment.character_start_times_seconds,
                    alignment.character_end_times_seconds,
                    strict=True,
                )
            )
            measured = MeasuredSpeech(
                pcm, settings.sample_rate, characters, response.headers.get("request-id")
            )
            output = io.BytesIO()
            with wave.open(output, "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(settings.sample_rate)
                audio.writeframes(pcm)
            return SynthesizedSpeech(measured, output.getvalue())
        except httpx.HTTPStatusError as exc:
            # Recognize only a fixed error code; never expose provider messages,
            # which may echo credentials or private narration.
            try:
                failure = exc.response.json()
            except ValueError:
                failure = None
            detail = failure.get("detail") if isinstance(failure, dict) else None
            if isinstance(detail, dict) and "quota_exceeded" in (
                detail.get("code"),
                detail.get("status"),
            ):
                raise SpeechUnavailable(
                    "ElevenLabs narration credits are exhausted. Add credits, then continue "
                    "video generation. Your saved script is unchanged."
                ) from exc
            # Never return provider bodies: they may echo credentials or private narration.
            raise SpeechUnavailable(
                f"ElevenLabs speech request failed (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.HTTPError as exc:
            # Ambiguous failures are not automatically billed again.
            raise SpeechUnavailable("ElevenLabs speech request failed; retry the stage") from exc
        except (ValueError, binascii.Error, ValidationError, AlignmentError) as exc:
            raise SpeechUnavailable("ElevenLabs returned unusable audio or alignment") from exc
