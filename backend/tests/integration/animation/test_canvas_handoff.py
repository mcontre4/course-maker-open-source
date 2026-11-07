import json
from dataclasses import replace

import pytest

from app.courses.adapters.ai.canvas_delivery import CanvasDelivery
from app.courses.adapters.http.schema import CourseInput
from app.courses.adapters.http.standalone import CreateLessonInput
from app.courses.adapters.video.local import LocalLessonVideo
from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.ports.animator import AnimationUnavailable
from app.courses.ports.animator_model import AnimatorModel

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
def test_plain_js_handoff_has_exact_reference_and_cached_review_policy(canvas_runtime, style_id):
    animator, commands, inputs, root = canvas_runtime
    inputs = replace(inputs, visual_style_id=style_id)
    project = animator.generate(inputs)
    source = root / project.project_key
    assert project.project_key.endswith("/javascript")
    assert not (source / "src/Root.tsx").exists()
    assert (source / "style/harness.js").read_bytes() == (
        commands.tools / "styles" / style_id / "harness.js"
    ).read_bytes()
    assert (source / "style/reference.png").is_file()
    assert animator.generate(replace(inputs, review_output=False)) == project
    assert animator.generate(replace(inputs, animator_model=AnimatorModel.SOL)) == project
    assert commands.calls == ["author-0", "validate-0"]


def test_interrupted_authoring_rebuilds_trusted_files_and_allows_source_repair(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    commands.fail_author_once = True
    with pytest.raises(AnimationUnavailable, match="Interrupted authoring"):
        animator.generate(inputs)
    project = animator.generate(inputs)
    source = root / project.project_key
    assert commands.authoring_round == 2
    assert "authoring round 2" in (source / "animation.js").read_text()
    assert (source / "style/drawing.js").read_bytes() == (
        commands.tools / "styles/flat-vector-science/drawing.js"
    ).read_bytes()
    assert not (source / "unexpected.js").exists()
    assert not (source.parent / "change-request.json").exists()
    animator.verify(project)


def test_agent_cannot_modify_reference(canvas_runtime):
    animator, commands, inputs, _ = canvas_runtime
    commands.tamper = True
    with pytest.raises(AnimationUnavailable, match="protected"):
        animator.generate(inputs)


def test_invalid_first_draft_does_not_start_another_authoring_pass(canvas_runtime):
    animator, commands, inputs, _ = canvas_runtime
    commands.invalid_source = True
    with pytest.raises(AnimationUnavailable):
        animator.generate(inputs)
    assert commands.authoring_round == 1
    assert commands.calls == ["author-0", "validate-0"]


@pytest.mark.parametrize("review", [True, False])
def test_delivery_render_cache_playback_and_honest_status(canvas_runtime, review):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(inputs)
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    announced = []

    def source_ready():
        assert ("visual-review" in commands.calls) is review
        assert "render-final" not in commands.calls
        announced.append(project)

    assert delivery.deliver(project, review=review, source_ready=source_ready).approved
    assert announced == [project]
    assert ("visual-review" in commands.calls) is review
    assert delivery.deliver(
        project, review=review, source_ready=lambda: announced.append(project)
    ).approved
    assert announced == [project, project]
    assert commands.calls.count("render-review") == int(review)
    assert commands.calls.count("render-final") == 1
    saved = replace(project, review_status="approved" if review else "skipped")
    assert LocalLessonVideo(root, "canvas-test").read(saved) == b"rendered-canvas-video"


def test_low_style_scores_are_advisory_and_do_not_veto_delivery(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    commands.bad_quality = True
    project = animator.generate(inputs)
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    assert delivery.deliver(project, review=True).approved
    assert delivery.deliver(project, review=True).approved
    assert commands.calls.count("visual-review") == 1
    assert commands.calls.count("render-final") == 1
    assert (
        LocalLessonVideo(root, "canvas-test").read(replace(project, review_status="approved"))
        == b"rendered-canvas-video"
    )


def test_interrupted_final_encode_reuses_review_and_replaces_partial_video(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(inputs)
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    commands.fail_final_once = True
    with pytest.raises(AnimationUnavailable, match="Final encoder interrupted"):
        delivery.deliver(project, review=True)
    assert delivery.deliver(project, review=True).approved
    assert commands.calls.count("visual-review") == 1
    assert commands.calls.count("render-final") == 2
    assert (
        LocalLessonVideo(root, "canvas-test").read(replace(project, review_status="approved"))
        == b"rendered-canvas-video"
    )


@pytest.mark.parametrize("reuse_render", [False, True])
def test_reviewer_created_video_does_not_skip_final_technical_validation(
    canvas_runtime, reuse_render
):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(inputs)
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    if reuse_render:
        assert delivery.deliver(project, review=False).approved
    commands.reviewer_writes_video = True
    assert delivery.deliver(project, review=True).approved
    assert commands.calls.count("render-final") == 1 + int(reuse_render)
    assert (
        LocalLessonVideo(root, "canvas-test").read(replace(project, review_status="approved"))
        == b"rendered-canvas-video"
    )


def test_one_consolidated_review_and_repair_delivers_exact_verified_video(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    commands.bad_quality = True
    commands.review_findings = True
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    published = []

    def source_ready(project):
        assert commands.calls.count("visual-review") == 1
        assert commands.calls.count("repair-0") == 1
        assert "render-final" not in commands.calls
        published.append(project)

    response = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, source_ready=source_ready))
    )
    assert len(published) == 1
    assert published[0].output_hash == response.project.output_hash
    assert response.project.review_status == "repaired"
    assert commands.authoring_round == 2
    assert commands.calls.count("visual-review") == 1
    assert commands.calls.count("repair-0") == 1
    decisions = [json.loads(p.read_text()) for p in (root / ".review-state").glob("*/result.json")]
    assert {d["review_status"] for d in decisions} == {"rejected", "repaired"}
    repaired = next(d for d in decisions if d["review_status"] == "repaired")
    assert repaired["approved"] is False
    assert "No second AI review" in repaired["feedback"]
    assert LocalLessonVideo(root, "canvas-test").read(response.project) == b"rendered-canvas-video"
    calls = list(commands.calls)
    again = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(inputs)
    )
    assert again.project == response.project
    assert commands.calls == calls
    assert delivery.deliver(response.project, review=False).approved
    assert commands.calls == calls  # A review preference change reuses repaired playback.


def test_missing_input_during_visual_repair_still_produces_playable_original(
    canvas_runtime, caplog
):
    animator, commands, inputs, root = canvas_runtime
    commands.review_findings = True
    commands.change_on_repair = True
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    response = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(inputs)
    )
    assert response.project.review_status == "repaired"
    assert LocalLessonVideo(root, "canvas-test").read(response.project) == b"rendered-canvas-video"
    assert commands.calls.count("visual-review") == 1
    assert commands.calls.count("repair-0") == 1
    reports = [json.loads(p.read_text()) for p in (root / ".review-state").glob("*/result.json")]
    assert {r["review_status"] for r in reports} == {"rejected", "repaired"}
    assert (
        next(r for r in reports if r["review_status"] == "repaired")["validation"]
        == "visual_repaired"
    )


def test_missing_map_data_during_authoring_still_delivers_video(canvas_runtime):
    from dataclasses import replace

    animator, commands, inputs, root = canvas_runtime
    commands.change_on_author = True
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    response = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, review_output=False))
    )
    assert LocalLessonVideo(root, "canvas-test").read(response.project) == b"rendered-canvas-video"
    source = root / response.project.project_key / "animation.js"
    assert inputs.storyboard.scenes[0].cues[0].anchor_text in source.read_text()
    assert commands.calls.count("author-0") == 1
    assert commands.calls.count("author-best-effort") == 1
    assert not (source.parent.parent / "change-request.json").exists()


def test_invalid_visual_report_does_not_block_final_video(canvas_runtime, caplog):
    animator, commands, inputs, root = canvas_runtime
    commands.review_override = []
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    response = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(inputs)
    )
    assert response.project.review_status == "warning"
    assert LocalLessonVideo(root, "canvas-test").read(response.project) == b"rendered-canvas-video"
    assert "repair-0" not in commands.calls
    assert commands.calls.count("visual-review") == 1
    assert "non-blocking" in caplog.text


@pytest.mark.parametrize(
    "report",
    [
        [],
        {"quality": [4, 4, 4, 4]},
        {
            "approved": True,
            "feedback": "Invalid observations",
            "quality": dict.fromkeys(
                (
                    "style_fidelity",
                    "illustration",
                    "composition",
                    "continuity",
                    "explanation",
                    "visual_development",
                    "pacing",
                ),
                4,
            ),
            "scene_checks": [{"scene_id": "s01", "observations": 42}],
        },
    ],
)
def test_malformed_reviewer_output_fails_at_boundary(canvas_runtime, report):
    animator, commands, inputs, root = canvas_runtime
    commands.review_override = report
    project = animator.generate(inputs)
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    with pytest.raises(AnimationUnavailable, match="Missing or incomplete visual review"):
        delivery.deliver(project, review=True)


def test_enabling_review_reuses_exact_validated_render_but_calls_reviewer(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(inputs)
    delivery = CanvasDelivery(root, ["author", "-"], commands, commands, "canvas-test")
    assert delivery.deliver(project, review=False).approved
    assert delivery.deliver(project, review=True).approved
    assert commands.calls.count("render-final") == 1
    assert commands.calls.count("render-review") == 0
    assert commands.calls.count("visual-review") == 1


@pytest.mark.parametrize(
    "schema,payload",
    [
        (CreateLessonInput, {"title": "History", "description": "Silk Roads", "minutes": 1}),
        (
            CourseInput,
            {
                "title": "History",
                "description": "Silk Roads",
                "duration": {"mode": "total", "hours": 1},
            },
        ),
    ],
)
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
def test_creation_requires_explicit_supported_style(schema, payload, style_id):
    with pytest.raises(ValueError):
        schema.model_validate(payload)
    with pytest.raises(ValueError):
        schema.model_validate({**payload, "style": {"visualStyleId": "unavailable"}})
    selected = schema.model_validate(
        {
            **payload,
            "style": {
                "visualStyleId": style_id,
                "reviewOutput": False,
            },
        }
    )
    assert selected.style.to_request().visual_style_id == style_id
    assert selected.style.to_request().review_output is False


def test_watercolor_handoff_preserves_package_and_embeds_local_fonts(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(replace(inputs, visual_style_id="watercolor-wash"))
    source = root / project.project_key
    package = commands.tools / "styles/watercolor-wash"
    for name in ("source-prompt.txt", "drawing.js", "sound.js", "examples/reference-ai.js"):
        assert (source / "style" / name).read_bytes() == (package / name).read_bytes()
    for weight in (400, 700):
        font = f"caveat-latin-{weight}-normal.woff2"
        assert (source / "fonts" / font).read_bytes() == (
            commands.tools / "node_modules/@fontsource/caveat/files" / font
        ).read_bytes()
    assert animator.generate(inputs).input_hash != project.input_hash


def test_tech_glow_handoff_preserves_reference_and_fonts(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(replace(inputs, visual_style_id="tech-glow"))
    source = root / project.project_key
    package = commands.tools / "styles/tech-glow"
    for name in ("source-prompt.txt", "drawing.js", "sound.js", "examples/reference-ai.js"):
        assert (source / "style" / name).read_bytes() == (package / name).read_bytes()
    for family, weights in (
        ("inter", (300, 400, 500, 600, 800)),
        ("space-grotesk", (400, 500, 700)),
    ):
        for weight in weights:
            font = f"{family}-latin-{weight}-normal.woff2"
            assert (source / "fonts" / font).read_bytes() == (
                commands.tools / "node_modules/@fontsource" / family / "files" / font
            ).read_bytes()
    assert animator.generate(inputs).input_hash != project.input_hash


def test_whiteboard_handoff_preserves_reference_and_fonts(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(replace(inputs, visual_style_id="whiteboard"))
    source = root / project.project_key
    package = commands.tools / "styles/whiteboard"
    for name in ("source-prompt.txt", "drawing.js", "sound.js", "examples/reference-ai.js"):
        assert (source / "style" / name).read_bytes() == (package / name).read_bytes()
    for family, weight in (("permanent-marker", 400), ("kalam", 700)):
        font = f"{family}-latin-{weight}-normal.woff2"
        assert (source / "fonts" / font).read_bytes() == (
            commands.tools / "node_modules/@fontsource" / family / "files" / font
        ).read_bytes()
    assert animator.generate(inputs).input_hash != project.input_hash


def test_halftone_handoff_preserves_reference_and_font(canvas_runtime):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(replace(inputs, visual_style_id="halftone-pop"))
    source = root / project.project_key
    package = commands.tools / "styles/halftone-pop"
    for name in ("source-prompt.txt", "drawing.js", "sound.js", "examples/reference-ai.js"):
        assert (source / "style" / name).read_bytes() == (package / name).read_bytes()
    font = "bangers-latin-400-normal.woff2"
    assert (source / "fonts" / font).read_bytes() == (
        commands.tools / "node_modules/@fontsource/bangers/files" / font
    ).read_bytes()
    assert animator.generate(inputs).input_hash != project.input_hash


@pytest.mark.parametrize(
    "style_id,fonts",
    [
        ("risograph", (("archivo-black", 400), ("space-mono", 400), ("space-mono", 700))),
        ("gouache-poster", (("bebas-neue", 400), ("oswald", 400), ("oswald", 700))),
        ("soft-3d", (("fredoka", 600), ("fredoka", 700))),
        ("memphis", (("rubik-mono-one", 400), ("fredoka", 700))),
        ("bauhaus", (("space-grotesk", 400), ("space-grotesk", 700), ("syne", 800))),
        ("swiss-grid", (("inter", 400), ("inter", 600), ("inter", 800))),
    ],
)
def test_uploaded_style_handoff_preserves_package_and_local_fonts(canvas_runtime, style_id, fonts):
    animator, commands, inputs, root = canvas_runtime
    project = animator.generate(replace(inputs, visual_style_id=style_id))
    source = root / project.project_key
    package = commands.tools / "styles" / style_id
    for original in package.rglob("*"):
        if original.is_file():
            assert (
                source / "style" / original.relative_to(package)
            ).read_bytes() == original.read_bytes()
    for family, weight in fonts:
        font = f"{family}-latin-{weight}-normal.woff2"
        assert (source / "fonts" / font).read_bytes() == (
            commands.tools / "node_modules/@fontsource" / family / "files" / font
        ).read_bytes()
        assert font in (source / "player.html").read_text()
    assert animator.generate(inputs).input_hash != project.input_hash
