"""Measured speech, independent of provider, transport and storage implementations."""

import math
import re
from dataclasses import dataclass

from app.courses.domain.errors import CourseError
from app.courses.domain.storyboard import Storyboard, StoryboardScene


class AlignmentError(CourseError):
    """Speech cannot safely drive the animation timeline."""


@dataclass(frozen=True)
class SpeechSettings:
    voice_id: str
    stability: float = 0.5
    similarity: float = 0.75
    clone_strength: float = 0.0
    model_id: str = "eleven_v4"
    sample_rate: int = 24000
    delivery: str = ""

    def __post_init__(self) -> None:
        if len(self.delivery) > 200 or any(c in self.delivery for c in "[]\n\r"):
            raise CourseError("Invalid voice delivery direction")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", self.voice_id):
            raise CourseError("Configure a valid ElevenLabs voice ID")
        if self.model_id != "eleven_v4" or self.sample_rate != 24000:
            raise CourseError("Speech requires Eleven v4 and 24 kHz PCM")
        for value in (self.stability, self.similarity, self.clone_strength):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise CourseError("Voice settings must be finite values between zero and one")


@dataclass(frozen=True)
class TimedText:
    text: str
    start_sec: float
    end_sec: float

    def __post_init__(self) -> None:
        if (
            not self.text
            or not math.isfinite(self.start_sec)
            or not math.isfinite(self.end_sec)
            or not 0 <= self.start_sec <= self.end_sec
        ):
            raise AlignmentError("Invalid measured text interval")


@dataclass(frozen=True)
class CueTiming:
    id: str
    anchor_text: str
    start_sec: float
    end_sec: float

    def __post_init__(self) -> None:
        TimedText(self.anchor_text, self.start_sec, self.end_sec)
        if not self.id:
            raise AlignmentError("Cue timing requires its original identifier")


@dataclass(frozen=True)
class MeasuredSpeech:
    pcm: bytes
    sample_rate: int
    characters: tuple[TimedText, ...]
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not self.pcm or len(self.pcm) % 2 or self.sample_rate != 24000:
            raise AlignmentError("Expected nonempty mono 16-bit 24 kHz PCM")
        if not self.characters:
            raise AlignmentError("Provider returned no original-text alignment")
        previous_start, previous_end = 0.0, 0.0
        for character in self.characters:
            if (
                len(character.text) != 1
                or character.start_sec < previous_start
                or character.end_sec < previous_end
                or character.end_sec > self.duration_sec
                or (character.text.isalnum() and character.end_sec <= character.start_sec)
            ):
                raise AlignmentError("Incomplete, nonmonotonic or out-of-audio alignment")
            previous_start, previous_end = character.start_sec, character.end_sec

    @property
    def duration_sec(self) -> float:
        return len(self.pcm) / (2 * self.sample_rate)


@dataclass(frozen=True)
class AlignedScene:
    scene_id: str
    transcript: str
    input_hash: str
    audio_key: str
    audio_sha256: str
    duration_sec: float
    timeline_start_sec: float
    words: tuple[TimedText, ...]
    cues: tuple[CueTiming, ...]
    request_id: str | None

    def __post_init__(self) -> None:
        if (
            not self.scene_id
            or not self.transcript
            or not self.audio_key
            or not math.isfinite(self.duration_sec)
            or self.duration_sec <= 0
            or not math.isfinite(self.timeline_start_sec)
            or self.timeline_start_sec < 0
            or not self.words
        ):
            raise AlignmentError("Invalid aligned scene")
        for digest in (self.input_hash, self.audio_sha256):
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise AlignmentError("Audio versions require SHA-256 hashes")
        if len({cue.id for cue in self.cues}) != len(self.cues):
            raise AlignmentError("Duplicate aligned cue IDs")
        if any(item.end_sec > self.duration_sec for item in self.words) or any(
            item.end_sec > self.duration_sec for item in self.cues
        ):
            raise AlignmentError("Text timing exceeds measured audio duration")


def align_scene(
    scene: StoryboardScene,
    speech: MeasuredSpeech,
    input_hash: str,
    audio_key: str,
    audio_sha256: str,
) -> AlignedScene:
    """Resolve exact character spans; never interpolate or guess missing anchors."""
    if "".join(c.text for c in speech.characters) != scene.narration_text:
        raise AlignmentError("Original-text alignment does not match verbatim narration")
    words = tuple(
        TimedText(
            m.group(),
            round(speech.characters[m.start()].start_sec, 9),
            round(speech.characters[m.end() - 1].end_sec, 9),
        )
        for m in re.finditer(r"\S+", scene.narration_text)
    )
    cues = []
    for cue in scene.cues:
        start = scene.narration_text.index(cue.anchor_text)
        end = start + len(cue.anchor_text)
        cues.append(
            CueTiming(
                cue.id,
                cue.anchor_text,
                round(speech.characters[start].start_sec, 9),
                round(speech.characters[end - 1].end_sec, 9),
            )
        )
    return AlignedScene(
        scene.scene_id,
        scene.narration_text,
        input_hash,
        audio_key,
        audio_sha256,
        round(speech.duration_sec, 9),
        0.0,
        words,
        tuple(cues),
        speech.request_id,
    )


@dataclass(frozen=True)
class LessonAlignment:
    lesson_id: str
    storyboard_hash: str
    settings: SpeechSettings
    silence_between_scenes_sec: float
    scenes: tuple[AlignedScene, ...]
    alignment_key: str
    status: str = "audio_aligned"
    version: str = "speech-v1"

    def __post_init__(self) -> None:
        if (
            self.status != "audio_aligned"
            or self.version != "speech-v1"
            or not self.scenes
            or not self.alignment_key
            or not re.fullmatch(r"[0-9a-f]{64}", self.storyboard_hash)
            or not math.isfinite(self.silence_between_scenes_sec)
            or not 0 <= self.silence_between_scenes_sec <= 5
        ):
            raise AlignmentError("Invalid lesson alignment manifest")
        offset = 0.0
        for scene in self.scenes:
            if not math.isclose(scene.timeline_start_sec, offset, abs_tol=1e-8):
                raise AlignmentError("Scene offsets must include measured audio and silence")
            offset = round(offset + scene.duration_sec + self.silence_between_scenes_sec, 9)

    def validate_storyboard(self, storyboard: Storyboard) -> None:
        if self.lesson_id != storyboard.lesson_id or len(self.scenes) != len(storyboard.scenes):
            raise AlignmentError("Alignment must belong to its complete storyboard")
        for aligned, scene in zip(self.scenes, storyboard.scenes, strict=True):
            if (aligned.scene_id, aligned.transcript) != (scene.scene_id, scene.narration_text):
                raise AlignmentError("Script changes invalidate narration audio")
            if tuple((c.id, c.anchor_text) for c in aligned.cues) != tuple(
                (c.id, c.anchor_text) for c in scene.cues
            ):
                raise AlignmentError("Alignment must preserve every original cue")

    @property
    def duration_sec(self) -> float:
        return round(self.scenes[-1].timeline_start_sec + self.scenes[-1].duration_sec, 9)
