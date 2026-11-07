import hashlib
import json
from dataclasses import replace

import pytest

from app.courses.adapters.ai.animation_project import project_digest
from app.courses.adapters.video.local import LocalLessonVideo
from app.courses.domain.animation import AnimationProject
from app.courses.ports.lesson_video import LessonVideoUnavailable

pytestmark = pytest.mark.integration


def test_reuses_the_exact_independently_approved_video(reviewed_video):
    root, project, _, _, _ = reviewed_video
    assert (
        LocalLessonVideo(root, "renderer-test-v1").read(project) == b"independently-reviewed-video"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("approved", False),
        ("source_hash", "e" * 64),
        ("renderer_version", "different-renderer"),
        ("video_sha256", "f" * 64),
        ("video_key", "../../outside.mp4"),
        ("video_key", 123),
    ],
)
def test_invalid_review_never_substitutes_unverified_media(reviewed_video, field, value):
    root, project, decision, report, _ = reviewed_video
    report[field] = value
    decision.write_text(json.dumps(report))
    assert LocalLessonVideo(root, "renderer-test-v1").read(project) == b"legacy-cached-video"


@pytest.mark.parametrize("report", [None, [], True, "invalid"])
def test_non_object_review_metadata_does_not_break_playback(reviewed_video, report):
    root, project, decision, _, _ = reviewed_video
    decision.write_text(json.dumps(report))
    assert LocalLessonVideo(root, "renderer-test-v1").read(project) == b"legacy-cached-video"


def test_tampered_approved_video_is_not_reused(reviewed_video):
    root, project, _, _, video = reviewed_video
    video.write_bytes(b"modified")
    assert LocalLessonVideo(root, "renderer-test-v1").read(project) == b"legacy-cached-video"


def test_cached_video_is_read_without_invoking_docker_or_modifying_source(tmp_path):
    project = AnimationProject("lesson", "a" * 64, "a" * 64 + "/remotion", "b" * 64, "test", 60)
    source = tmp_path / project.project_key
    source.mkdir(parents=True)
    (source / "scene.tsx").write_text("saved source")
    project = replace(project, output_hash=project_digest(source))
    key = hashlib.sha256((project.output_hash + "renderer-test-v1").encode()).hexdigest()
    cache = tmp_path / ".playback" / key
    cache.mkdir(parents=True)
    (cache / "lesson.mp4").write_bytes(b"previously-rendered-mp4")
    adapter = LocalLessonVideo(tmp_path, "renderer-test-v1")
    assert adapter.read_ready(project) == b"previously-rendered-mp4"
    assert adapter.read(project) == b"previously-rendered-mp4"
    assert (source / "scene.tsx").read_text() == "saved source"


def test_missing_source_is_a_retryable_application_error(tmp_path):
    project = AnimationProject("lesson", "a" * 64, "a" * 64 + "/remotion", "b" * 64, "test", 60)
    with pytest.raises(LessonVideoUnavailable, match="missing or invalid"):
        LocalLessonVideo(tmp_path, "renderer-test-v1").read(project)


def test_source_cannot_escape_artifact_storage_through_symlink(tmp_path):
    project = AnimationProject("lesson", "a" * 64, "a" * 64 + "/remotion", "b" * 64, "test", 60)
    outside = tmp_path / "outside"
    outside.mkdir()
    source = tmp_path / "artifacts"
    (source / ("a" * 64)).mkdir(parents=True)
    (source / project.project_key).symlink_to(outside)
    with pytest.raises(LessonVideoUnavailable, match="missing or invalid"):
        LocalLessonVideo(source, "renderer-test-v1").read(project)


def test_modified_source_is_rejected_before_using_cached_media(tmp_path):
    project = AnimationProject("lesson", "a" * 64, "a" * 64 + "/remotion", "b" * 64, "test", 60)
    source = tmp_path / project.project_key
    source.mkdir(parents=True)
    (source / "scene.tsx").write_text("changed after generation")
    with pytest.raises(LessonVideoUnavailable, match="checksum"):
        LocalLessonVideo(tmp_path, "renderer-test-v1").read(project)


def test_unavailable_cache_storage_maps_to_retryable_playback_error(tmp_path):
    source = tmp_path / ("a" * 64) / "remotion"
    source.mkdir(parents=True)
    (source / "scene.tsx").write_text("saved source")
    project = AnimationProject("lesson", "a" * 64, "a" * 64 + "/remotion", "b" * 64, "test", 60)
    project = replace(project, output_hash=project_digest(source))
    (tmp_path / ".playback").write_text("Cache directory is unavailable")
    with pytest.raises(LessonVideoUnavailable, match="storage is unavailable"):
        LocalLessonVideo(tmp_path, "renderer-test-v1").read(project)


def test_ready_check_never_encodes_a_missing_video(reviewed_video):
    root, project, decision, _, video = reviewed_video
    decision.unlink()
    video.unlink()
    pending = replace(project, review_status="pending")
    assert LocalLessonVideo(root, "renderer-test-v1").read_ready(pending) is None
    assert not video.exists()


def test_finished_artifact_is_ready_before_final_metadata_is_saved(reviewed_video):
    root, project, _, _, _ = reviewed_video
    pending = replace(project, review_status="pending")
    assert (
        LocalLessonVideo(root, "renderer-test-v1").read_ready(pending)
        == b"independently-reviewed-video"
    )
