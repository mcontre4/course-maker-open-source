"""Shared checkpointed speech pipeline; callers own persistence and authorization."""

import hashlib
import json
from dataclasses import asdict, replace

from app.courses.application.generate_storyboard import artifact_hash
from app.courses.domain.errors import CourseConflict
from app.courses.domain.speech import LessonAlignment, SpeechSettings, align_scene
from app.courses.domain.storyboard import StoryboardScene
from app.courses.domain.syllabus import Lesson
from app.courses.ports.speech import SpeechArtifacts, SpeechArtifactUnavailable, SpeechSynthesizer

SPEECH_PIPELINE_VERSION = "speech-v2"


def _scene_input_hash(scene: StoryboardScene, settings: SpeechSettings) -> str:
    return artifact_hash(
        {
            "scene_id": scene.scene_id,
            "text": scene.narration_text,
            "cues": [(c.id, c.anchor_text) for c in scene.cues],
            "settings": asdict(settings),
            "version": SPEECH_PIPELINE_VERSION,
        }
    )


def has_current_speech(lesson: Lesson) -> bool:
    alignment, board = lesson.alignment, lesson.storyboard
    if alignment is None or board is None or len(alignment.scenes) != len(board.scenes):
        return False
    return (
        alignment.storyboard_hash == artifact_hash(asdict(board))
        and all(
            aligned.scene_id == scene.scene_id
            and aligned.input_hash == _scene_input_hash(scene, alignment.settings)
            for scene, aligned in zip(board.scenes, alignment.scenes, strict=True)
        )
    )


def generate_lesson_speech(
    lesson: Lesson,
    synthesizer: SpeechSynthesizer,
    artifacts: SpeechArtifacts,
    settings: SpeechSettings,
    gap: float,
    prefix: str,
) -> LessonAlignment:
    if lesson.alignment is not None and has_current_speech(lesson):
        # Validate durable objects after closing the read transaction. A metadata
        # cache hit must not report success for missing or damaged media.
        expected_manifest = asdict(lesson.alignment)
        manifest = artifacts.read(lesson.alignment.alignment_key)
        try:
            saved_manifest = json.loads(manifest) if manifest is not None else None
            if isinstance(saved_manifest, dict) and isinstance(
                saved_manifest.get("settings"), dict
            ):
                # Older manifests predate expressive delivery; an absent direction means neutral.
                saved_manifest["settings"].setdefault("delivery", "")
            manifest_matches = saved_manifest == json.loads(json.dumps(expected_manifest))
        except (ValueError, UnicodeDecodeError):
            manifest_matches = False
        transcript_key = (
            lesson.alignment.alignment_key.removesuffix("alignment.json") + "transcript.txt"
        )
        transcript = artifacts.read(transcript_key)
        expected_transcript = "\n\n".join(s.transcript for s in lesson.alignment.scenes).encode()
        if not manifest_matches or transcript != expected_transcript:
            raise SpeechArtifactUnavailable("Saved speech artifacts are incomplete or corrupt")
        for cached_scene in lesson.alignment.scenes:
            audio = artifacts.read(cached_scene.audio_key)
            if audio is None or hashlib.sha256(audio).hexdigest() != cached_scene.audio_sha256:
                raise SpeechArtifactUnavailable("Saved speech audio is missing or corrupt")
        return lesson.alignment
    board = lesson.storyboard
    assert board is not None
    # Preflight the whole lesson before making any paid requests.
    if any(len(s.narration_text) > 10000 for s in board.scenes):
        raise CourseConflict("Eleven v4 scenes must contain at most 10,000 characters")
    if sum(len(s.narration_text) for s in board.scenes) > 100000:
        raise CourseConflict("Speech generation is capped at 100,000 characters per lesson")
    board_hash = artifact_hash(asdict(board))
    version = artifact_hash(
        {
            "board": board_hash,
            "settings": asdict(settings),
            "gap": gap,
            "timeline_precision": 9,
            "version": SPEECH_PIPELINE_VERSION,
        }
    )
    scenes = []
    offset = 0.0
    for scene in board.scenes:
        # Include only speech inputs: visual edits do not incur another TTS charge.
        input_hash = _scene_input_hash(scene, settings)
        checkpoint = f"{prefix}/scenes/{input_hash}.json"
        aligned = artifacts.read_scene(checkpoint)
        if aligned is not None:
            audio = artifacts.read(aligned.audio_key)
            if (
                aligned.input_hash != input_hash
                or aligned.transcript != scene.narration_text
                or audio is None
                or hashlib.sha256(audio).hexdigest() != aligned.audio_sha256
            ):
                raise SpeechArtifactUnavailable("Saved speech checkpoint is incomplete or corrupt")
        else:
            generated = synthesizer.synthesize(scene.narration_text, settings)
            digest = hashlib.sha256(generated.audio_wav).hexdigest()
            audio_key = f"{prefix}/audio/{input_hash}-{digest}.wav"
            aligned = align_scene(scene, generated.measured, input_hash, audio_key, digest)
            artifacts.write(audio_key, generated.audio_wav, "audio/wav")
            artifacts.write_scene(checkpoint, aligned)
        scenes.append(replace(aligned, timeline_start_sec=offset))
        offset = round(offset + aligned.duration_sec + gap, 9)
    alignment = LessonAlignment(
        str(lesson.id),
        board_hash,
        settings,
        gap,
        tuple(scenes),
        f"{prefix}/{version}/alignment.json",
    )
    alignment.validate_storyboard(board)
    artifacts.write(
        alignment.alignment_key,
        json.dumps(asdict(alignment), ensure_ascii=False, sort_keys=True).encode(),
        "application/json",
    )
    transcript_key = alignment.alignment_key.removesuffix("alignment.json") + "transcript.txt"
    artifacts.write(
        transcript_key,
        "\n\n".join(scene.transcript for scene in alignment.scenes).encode(),
        "text/plain; charset=utf-8",
    )
    return alignment
