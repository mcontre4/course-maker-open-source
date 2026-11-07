from dataclasses import replace

import pytest

from app.courses.adapters.video.local import LocalLessonVideo
from app.courses.adapters.video.preview import LocalLessonPlayback
from app.courses.ports.lesson_video import LessonVideoUnavailable

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "style_id",
    [
        "flat-vector-science",
        "watercolor-wash",
        "tech-glow",
        "whiteboard",
        "halftone-pop",
        "risograph",
        "gouache-poster",
        "soft-3d",
        "memphis",
        "bauhaus",
        "swiss-grid",
    ],
)
def test_preview_packages_exact_source_audio_and_fonts_without_encoding(canvas_runtime, style_id):
    animator, commands, inputs, root = canvas_runtime
    inputs = replace(inputs, visual_style_id=style_id)
    project = replace(animator.generate(inputs), review_status="pending")
    calls = list(commands.calls)
    playback = LocalLessonPlayback(root, LocalLessonVideo(root, "canvas-test"))
    assert not playback.video_ready(project)
    html = playback.preview(project)
    assert 'src="animation.js"' not in html
    assert 'src="player.js"' not in html
    assert 'fetch("timeline.json")' not in html
    assert "data:audio/wav;base64," in html
    assert "data:font/woff2;base64," in html
    assert "window.explainer=(ctx,W,H,t)" in html
    assert 'channel: "lesson-preview"' in html
    assert "fake-key" not in html
    assert commands.calls == calls
    assert not (root / ".reviews").exists()
    assert not (root / ".playback").exists()


def test_corrupt_source_never_becomes_a_browser_preview(canvas_runtime):
    animator, _, inputs, root = canvas_runtime
    project = animator.generate(inputs)
    (root / project.project_key / "animation.js").write_text("Changed after validation")
    with pytest.raises(LessonVideoUnavailable, match="missing or invalid"):
        LocalLessonPlayback(root, LocalLessonVideo(root, "test")).preview(project)


def test_progress_dependency_is_excluded_before_serializing_inputs(canvas_runtime):
    from fakes.lesson_playback import UnserializableProgressSink

    animator, _, inputs, root = canvas_runtime
    project = animator.generate(replace(inputs, source_ready=UnserializableProgressSink()))
    stored = (root / project.project_key).parent / "inputs.json"
    assert "source_ready" not in stored.read_text()
