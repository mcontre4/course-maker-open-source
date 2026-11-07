from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.speech import AlignedScene, MeasuredSpeech, SpeechSettings


class SpeechUnavailable(Exception):
    pass


class SpeechArtifactUnavailable(Exception):
    pass


@dataclass(frozen=True)
class SynthesizedSpeech:
    measured: MeasuredSpeech
    audio_wav: bytes


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str, settings: SpeechSettings) -> SynthesizedSpeech: ...


class SpeechArtifacts(Protocol):
    """Private durable objects; keys are relative logical artifact names, never public URLs."""

    def read(self, key: str) -> bytes | None: ...

    def write(self, key: str, content: bytes, content_type: str) -> None: ...

    def read_scene(self, key: str) -> AlignedScene | None: ...

    def write_scene(self, key: str, scene: AlignedScene) -> None: ...
