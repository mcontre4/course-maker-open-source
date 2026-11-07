import json
import math
import shutil
from dataclasses import replace

import pytest
from fixtures.animation import animation_inputs

from app.courses.adapters.ai.animation_project import (
    preflight,
    stage,
    timing_manifest,
    validate_files,
)
from app.courses.ports.animator import AnimationUnavailable

pytestmark = pytest.mark.integration


def test_preserves_audio_and_canonical_timeline(animation_files):
    inputs, job, protected = animation_files
    preflight(inputs)
    validate_files(inputs, job, protected)
    timeline = json.loads((job / "remotion/src/timeline.json").read_text())
    assert timeline["duration_frames"] == math.ceil(inputs.alignment.duration_sec * 30)
    for scene, record in zip(inputs.alignment.scenes, timeline["scenes"], strict=True):
        assert record["start_sec"] == scene.timeline_start_sec
        assert (job / f"remotion/public/audio/{scene.scene_id}.wav").read_bytes() in inputs.audio
        for cue, mapped in zip(scene.cues, record["cues"], strict=True):
            assert abs(mapped["start_frame"] / 30 - cue.start_sec) <= 1 / 60
            assert (
                abs(
                    mapped["absolute_start_frame"] / 30 - (scene.timeline_start_sec + cue.start_sec)
                )
                <= 1 / 30
            )


@pytest.mark.parametrize(
    "mutation", ["input", "audio", "timing", "cue", "event", "scene", "symlink"]
)
def test_rejects_changed_inputs_incomplete_scenes_and_bad_manifest(animation_files, mutation):
    inputs, job, protected = animation_files
    path = job / "remotion/scene-manifest.json"
    data = json.loads(path.read_text())
    if mutation == "input":
        (job / "inputs/storyboard.json").write_text("{}")
    elif mutation == "audio":
        (job / f"remotion/public/audio/{inputs.alignment.scenes[0].scene_id}.wav").write_bytes(
            b"bad"
        )
    elif mutation == "timing":
        data["scenes"][0]["cues"][0]["start_frame"] += 2
    elif mutation == "cue":
        data["scenes"][0]["cues"].pop()
    elif mutation == "event":
        data["scenes"][0]["cues"][0]["visual_event"] = " "
    elif mutation == "scene":
        (job / f"remotion/src/scenes/{inputs.storyboard.scenes[0].scene_id}.tsx").unlink()
    else:
        (job / "remotion/public/escape").symlink_to(job.parent)
    path.write_text(json.dumps(data))
    with pytest.raises(AnimationUnavailable):
        validate_files(inputs, job, protected)


def test_rejects_corrupt_audio_and_stale_storyboard_before_codex():
    inputs, _, _, _ = animation_inputs()
    with pytest.raises(AnimationUnavailable, match="checksum"):
        preflight(replace(inputs, audio=(b"corrupt", *inputs.audio[1:])))
    with pytest.raises(AnimationUnavailable, match="Stale"):
        preflight(replace(inputs, alignment=replace(inputs.alignment, storyboard_hash="e" * 64)))


def test_retry_cannot_write_inputs_through_a_worker_created_symlink(animation_files, tmp_path):
    inputs, job, _ = animation_files
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.rmtree(job / "inputs")
    (job / "inputs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AnimationUnavailable, match="Symlinks"):
        stage(inputs, job, job.parent / "tools")
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("name", ["final.mp4", "scene.html", "node_modules"])
def test_rejects_rendered_output_and_legacy_projects(animation_files, name):
    inputs, job, protected = animation_files
    (job / "remotion" / name).write_bytes(b"unexpected")
    with pytest.raises(AnimationUnavailable):
        validate_files(inputs, job, protected)


def test_frame_mapping_retains_silence_and_fractional_offsets(animation_files):
    inputs, _, _ = animation_files
    manifest = timing_manifest(inputs)
    assert [s["start_sec"] for s in manifest["scenes"]] == [
        s.timeline_start_sec for s in inputs.alignment.scenes
    ]
    assert manifest["duration_sec"] == inputs.alignment.duration_sec


def test_visual_timeline_covers_every_silent_gap_without_retiming_audio(animation_files):
    inputs, job, _ = animation_files
    timeline = timing_manifest(inputs)
    for current, following in zip(timeline["scenes"], timeline["scenes"][1:]):
        assert (
            current["start_frame"] + current["visual_duration_frames"] == following["start_frame"]
        )
    last = timeline["scenes"][-1]
    assert last["start_frame"] + last["visual_duration_frames"] == timeline["duration_frames"]
    root = (job / "remotion/src/Root.tsx").read_text()
    assert "Freeze" in root
    assert "<HoldScene" in root
    assert "<Audio src={staticFile(" in root
