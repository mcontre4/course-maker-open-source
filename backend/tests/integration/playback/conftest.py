import hashlib
import json
from dataclasses import replace

import pytest

from app.courses.adapters.ai.animation_project import project_digest
from app.courses.domain.animation import AnimationProject


@pytest.fixture
def reviewed_video(tmp_path):
    project = AnimationProject("lesson", "a" * 64, "a" * 64 + "/remotion", "b" * 64, "test", 60)
    source = tmp_path / project.project_key
    source.mkdir(parents=True)
    (source / "scene.tsx").write_text("saved source")
    project = replace(project, output_hash=project_digest(source))
    video_key = ".reviews/" + "c" * 64 + "/render/lesson.mp4"
    video = tmp_path / video_key
    video.parent.mkdir(parents=True)
    video.write_bytes(b"independently-reviewed-video")
    report = {
        "approved": True,
        "source_hash": project.output_hash,
        "renderer_version": "renderer-test-v1",
        "video_key": video_key,
        "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    }
    decision = tmp_path / ".review-state" / ("d" * 64) / "result.json"
    decision.parent.mkdir(parents=True)
    decision.write_text(json.dumps(report))
    fallback = (
        tmp_path
        / ".playback"
        / hashlib.sha256((project.output_hash + "renderer-test-v1").encode()).hexdigest()
    )
    fallback.mkdir(parents=True)
    (fallback / "lesson.mp4").write_bytes(b"legacy-cached-video")
    return tmp_path, project, decision, report, video
