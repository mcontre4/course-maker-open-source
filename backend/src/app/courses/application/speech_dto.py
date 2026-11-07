from dataclasses import dataclass

from app.courses.domain.speech import LessonAlignment


@dataclass(frozen=True)
class TimedTextResponse:
    text: str
    start_sec: float
    end_sec: float


@dataclass(frozen=True)
class CueTimingResponse:
    id: str
    anchor_text: str
    start_sec: float
    end_sec: float


@dataclass(frozen=True)
class SpeechSettingsResponse:
    voice_id: str
    model_id: str
    sample_rate: int
    stability: float
    similarity: float
    clone_strength: float
    delivery: str = ""


@dataclass(frozen=True)
class AlignedSceneResponse:
    scene_id: str
    transcript: str
    audio_key: str
    duration_sec: float
    timeline_start_sec: float
    words: tuple[TimedTextResponse, ...]
    cues: tuple[CueTimingResponse, ...]


@dataclass(frozen=True)
class AlignmentResponse:
    lesson_id: str
    storyboard_hash: str
    alignment_key: str
    status: str
    settings: SpeechSettingsResponse
    silence_between_scenes_sec: float
    duration_sec: float
    scenes: tuple[AlignedSceneResponse, ...]


def alignment_response(alignment: LessonAlignment | None) -> AlignmentResponse | None:
    if alignment is None:
        return None
    settings = alignment.settings
    return AlignmentResponse(
        alignment.lesson_id,
        alignment.storyboard_hash,
        alignment.alignment_key,
        alignment.status,
        SpeechSettingsResponse(
            settings.voice_id,
            settings.model_id,
            settings.sample_rate,
            settings.stability,
            settings.similarity,
            settings.clone_strength,
            settings.delivery,
        ),
        alignment.silence_between_scenes_sec,
        alignment.duration_sec,
        tuple(
            AlignedSceneResponse(
                s.scene_id,
                s.transcript,
                s.audio_key,
                s.duration_sec,
                s.timeline_start_sec,
                tuple(TimedTextResponse(w.text, w.start_sec, w.end_sec) for w in s.words),
                tuple(
                    CueTimingResponse(c.id, c.anchor_text, c.start_sec, c.end_sec) for c in s.cues
                ),
            )
            for s in alignment.scenes
        ),
    )
