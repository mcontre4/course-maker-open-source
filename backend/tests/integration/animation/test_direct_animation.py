import base64
import json
from dataclasses import asdict, replace

import pytest

from app.courses.adapters.ai.canvas_delivery import CanvasDelivery
from app.courses.adapters.ai.direct_animation import DirectCanvasReviewer
from app.courses.adapters.video.local import LocalLessonVideo
from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.ports.animator import AnimationUnavailable


def test_direct_repair_requesting_more_input_is_advisory(direct_canvas_runtime, caplog):
    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [
        SOURCE,
        json.dumps(
            {
                "scene_ids": ["s01"],
                "reason": "Missing sourced map data",
                "requested_change": "Provide geographic data",
            }
        ),
    ]
    commands.review_findings = True
    delivery = CanvasDelivery(root, ["direct-review", "-"], commands, commands, "canvas-test")
    result = ProduceCanvasAnimation(author, delivery).execute(ProduceCanvasAnimationRequest(inputs))
    assert result.project.review_status == "repaired"
    assert (root / result.project.project_key / "animation.js").read_text() == SOURCE
    assert LocalLessonVideo(root, "canvas-test").read(result.project) == b"rendered-canvas-video"
    assert len(provider.requests) == 2


pytestmark = pytest.mark.integration


@pytest.mark.parametrize("style_id", ["flat-vector-science", "whiteboard"])
def test_history_reference_uses_compatible_executable_code(direct_canvas_runtime, style_id):
    from app.courses.application.generate_storyboard import artifact_hash

    author, provider, _, inputs, _ = direct_canvas_runtime
    purpose = "Trade routes connected cities through local exchange and intermediaries."
    board = replace(
        inputs.storyboard,
        scenes=tuple(
            replace(scene, learning_purpose=purpose) for scene in inputs.storyboard.scenes
        ),
    )
    aligned = replace(inputs.alignment, storyboard_hash=artifact_hash(asdict(board)))
    provider.outputs = [
        "window.explainer=(ctx,W,H,t)=>{ctx.fillRect(0,0,W,H);};"
        "window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];"
    ]
    author.generate(replace(inputs, visual_style_id=style_id, storyboard=board, alignment=aligned))
    content = provider.requests[0]["messages"][1]["content"]
    files = json.loads(content[0]["text"].rsplit("\n", 1)[1])
    assert json.loads(files["teaching-reference/sequence.json"])["id"] == "network"
    assert ("teaching-reference/animation.js" in files) == (style_id == "flat-vector-science")
    assert any("/examples/" in key for key in files) == (style_id == "whiteboard")


SOURCE = (
    "window.explainer=(ctx,W,H,t)=>{FV.sky(ctx,W,H,t);};"
    "window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];"
)


@pytest.mark.parametrize("cached_review", [False, True])
def test_scene_specific_review_findings_reach_actual_repair_request(
    direct_canvas_runtime, cached_review
):
    author, provider, commands, inputs, root = direct_canvas_runtime
    detailed_fix = "At 12.3s, bend the cyan connector below the capital caption."
    report = {
        "approved": False,
        "feedback": "Small presentation fixes are recommended.",
        "scene_checks": [
            {"scene_id": scene.scene_id, "observations": detailed_fix}
            for scene in inputs.alignment.scenes
        ],
        "quality": dict.fromkeys(
            [
                "style_fidelity",
                "illustration",
                "composition",
                "continuity",
                "explanation",
                "visual_development",
                "pacing",
            ],
            3,
        ),
    }
    provider.outputs = [SOURCE, json.dumps(report), SOURCE + "// repaired"]
    reviewer = DirectCanvasReviewer(author._llm)
    delivery = CanvasDelivery(root, reviewer.arguments(), reviewer.run_job, commands, "test")
    if cached_review:
        project = author.generate(inputs)
        rejected = delivery.deliver(project, review=True)
        assert not rejected.approved
        assert json.loads(rejected.feedback)["scene_checks"] == report["scene_checks"]
        inputs = replace(inputs, existing_project=project)
    result = ProduceCanvasAnimation(author, delivery).execute(ProduceCanvasAnimationRequest(inputs))
    assert result.project.review_status == "repaired"
    assert len(provider.requests) == 3
    supplied = provider.requests[-1]["messages"][1]["content"][0]["text"]
    assert detailed_fix in supplied
    saved = json.loads(
        (root / result.project.project_key).parent.joinpath("inputs.json").read_text()
    )
    findings = json.loads(saved["visual_feedback"])
    assert findings["scene_checks"] == report["scene_checks"]
    assert findings["quality"] == report["quality"]
    assert findings["feedback"] == report["feedback"]
    assert LocalLessonVideo(root, "test").read(result.project) == b"rendered-canvas-video"


@pytest.mark.parametrize(
    "direct_canvas_runtime", ["openai/gpt-6-luna", "openai/gpt-6-luna:fast"], indirect=True
)
def test_author_and_repair_use_one_request_each_and_no_cli(direct_canvas_runtime):
    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [SOURCE, SOURCE + "// repaired"]
    project = author.generate(inputs)
    assert project.backend == "direct"
    assert commands.calls == ["validate-0"]
    assert len(provider.requests) == 1
    payload = provider.requests[0]
    assert payload["model"] == "openai/gpt-6-luna"
    assert project.model == author._llm.model
    assert payload.get("service_tier") == ("priority" if project.model.endswith(":fast") else None)
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["max_tokens"] == 120000
    assert "tools" not in payload
    supplied = payload["messages"][1]["content"][0]["text"]
    assert all(
        name in supplied for name in ("timeline.json", "drawing.js", "harness.js", "sound.js")
    )
    assert author.generate(inputs) == project
    assert len(provider.requests) == 1
    repaired = author.generate(
        replace(inputs, visual_feedback="Move the label", previous_project_key=project.project_key)
    )
    assert len(provider.requests) == 2
    assert provider.requests[-1]["max_tokens"] == 120000
    assert repaired.input_hash != project.input_hash
    assert "Move the label" in provider.requests[-1]["messages"][1]["content"][0]["text"]
    assert (root / repaired.project_key / "animation.js").read_text().endswith("// repaired")


@pytest.mark.parametrize(
    "style_id,expected_example",
    [
        ("flat-vector-science", "silk-road.js"),
        ("watercolor-wash", "reference-ai.js"),
        ("tech-glow", "reference-ai.js"),
        ("whiteboard", "reference-ai.js"),
        ("halftone-pop", "reference-ai.js"),
        ("risograph", "reference-ai.js"),
        ("gouache-poster", "reference-ai.js"),
        ("soft-3d", "reference-ai.js"),
        ("memphis", "reference-ai.js"),
        ("bauhaus", "reference-ai.js"),
        ("swiss-grid", "reference-ai.js"),
    ],
)
def test_author_receives_selected_style_curated_example_and_pixels(
    direct_canvas_runtime, style_id, expected_example
):
    author, provider, commands, inputs, root = direct_canvas_runtime
    source = (
        "window.explainer=(ctx,W,H,t)=>{ctx.fillRect(0,0,W,H);};"
        "window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];"
    )
    provider.outputs = [source]
    project = author.generate(replace(inputs, visual_style_id=style_id))
    assert len(provider.requests) == 1
    content = provider.requests[0]["messages"][1]["content"]
    files = json.loads(content[0]["text"].rsplit("\n", 1)[1])
    example_key = "javascript/style/examples/" + expected_example
    assert [key for key in files if "/examples/" in key] == [example_key]
    package = commands.tools / "styles" / style_id
    assert files[example_key] == (package / "examples" / expected_example).read_text()
    assert files["javascript/style/STYLE.md"] == (package / "STYLE.md").read_text()
    supplied_inputs = json.loads(files["inputs.json"])
    assert supplied_inputs["visual_style_id"] == style_id
    assert supplied_inputs["storyboard"] == json.loads(json.dumps(asdict(inputs.storyboard)))
    images = [part["image_url"] for part in content if part["type"] == "image_url"]
    assert len(images) == 2 and all(image["detail"] == "high" for image in images)
    notes = json.loads(files["teaching-reference/sequence.json"])
    assert notes["id"] == "mechanism"
    assert "window.explainer" in files["teaching-reference/animation.js"]
    assert (
        base64.b64decode(images[0]["url"].split(",", 1)[1])
        == (package / "reference.png").read_bytes()
    )
    assert (root / project.project_key / "animation.js").read_text() == source
    assert commands.calls == ["validate-0"]


@pytest.mark.parametrize(
    "failure", ["invalid_source", "truncated", "http_error", "provider_error", "connection_error"]
)
def test_failed_authoring_does_not_retry(direct_canvas_runtime, failure):
    author, provider, commands, inputs, _ = direct_canvas_runtime
    provider.outputs = ["window.explainer = (" if failure == "invalid_source" else SOURCE]
    if failure == "truncated":
        provider.finish_reason = "length"
    if failure == "http_error":
        provider.status = 503
    if failure == "provider_error":
        provider.error_response = {"code": 502, "message": "Provider disconnected unexpectedly"}
    if failure == "connection_error":
        provider.connection_failure = True
    expected = {
        "invalid_source": "JavaScript authoring failed",
        "truncated": "120000-token output limit.*including reasoning",
        "http_error": "HTTP 503",
        "provider_error": "animation provider error \\(502\\): Provider disconnected unexpectedly",
        "connection_error": "animation connection failed \\(RemoteProtocolError\\)",
    }
    with pytest.raises(AnimationUnavailable, match=expected[failure]):
        author.generate(inputs)
    assert len(provider.requests) == 1
    assert not any(name.startswith("codex") for name in commands.calls)


@pytest.mark.parametrize("review", [True, False])
@pytest.mark.parametrize(
    "direct_canvas_runtime", ["openai/gpt-6-luna", "openai/gpt-6-luna:fast"], indirect=True
)
def test_direct_review_receives_pixels_and_uses_shared_report_validation(
    direct_canvas_runtime, review
):
    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [SOURCE]
    project = author.generate(inputs)
    provider.outputs = [
        json.dumps(
            {
                "approved": True,
                "feedback": "Clear scenes",
                "scene_checks": [
                    {"scene_id": scene.scene_id, "observations": "Readable illustration"}
                    for scene in inputs.alignment.scenes
                ],
                "quality": dict.fromkeys(
                    [
                        "style_fidelity",
                        "illustration",
                        "composition",
                        "continuity",
                        "explanation",
                        "visual_development",
                        "pacing",
                    ],
                    4,
                ),
            }
        )
    ]
    reviewer = DirectCanvasReviewer(author._llm)
    delivery = CanvasDelivery(root, reviewer.arguments(), reviewer.run_job, commands, "test")
    assert delivery.deliver(project, review=review).approved
    assert len(provider.requests) == 1 + int(review)
    assert delivery.deliver(project, review=review).approved
    assert len(provider.requests) == 1 + int(review)
    if review:
        content = provider.requests[-1]["messages"][1]["content"]
        assert sum(item["type"] == "image_url" for item in content) >= 2
        assert any(
            part["type"] == "image_url"
            and base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
            == b"rendered-motion-strip"
            for part in content
        )
        assert provider.requests[-1]["model"] == "openai/gpt-6-luna"
        assert provider.requests[-1].get("service_tier") == (
            "priority" if project.model.endswith(":fast") else None
        )
    assert "visual-review" not in commands.calls


def test_invalid_direct_review_fails_closed(direct_canvas_runtime):
    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [SOURCE, '{"approved":true,"feedback":"Looks good"}']
    project = author.generate(inputs)
    reviewer = DirectCanvasReviewer(author._llm)
    delivery = CanvasDelivery(root, reviewer.arguments(), reviewer.run_job, commands, "test")
    with pytest.raises(AnimationUnavailable, match="incomplete visual review"):
        delivery.deliver(project, review=True)
    assert len(provider.requests) == 2
    assert "render-final" not in commands.calls


@pytest.mark.parametrize("continuation", ["source", "change_request", "empty"])
def test_direct_author_delivers_without_requiring_storyboard_changes(
    direct_canvas_runtime, continuation
):
    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [
        json.dumps(
            {
                "scene_ids": [inputs.storyboard.scenes[0].scene_id],
                "reason": "Conflicting facts",
                "requested_change": "Clarify the fact",
            }
        )
    ]
    provider.outputs.append(
        {
            "source": SOURCE,
            "change_request": provider.outputs[0],
            "empty": "",
        }[continuation]
    )
    project = author.generate(inputs)
    assert project.status == "animation_ready"
    source = root / project.project_key / "animation.js"
    assert source.is_file()
    assert not (source.parent.parent / "change-request.json").exists()
    assert len(provider.requests) == 2
    assert commands.calls == ["validate-0"]
    assert author.generate(inputs) == project
    if continuation != "source":
        assert "window.cueEvents" in source.read_text()
        assert inputs.storyboard.scenes[0].cues[0].anchor_text in source.read_text()
        import subprocess

        # Execute the actual fallback drawing code at every cue, without a paid renderer.
        subprocess.run(
            [
                "node",
                "-e",
                """
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert');
const window = {}, context = vm.createContext({window});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const scenes = vm.runInContext('fallbackScenes', context);
for (const scene of scenes) for (const cue of scene.cues) {
  function draw() {
    const texts = [];
    const ctx = {fillRect(){}, measureText(s){return {width:s.length*24};},
      fillText(s){texts.push(s);}};
    window.explainer(ctx,1280,720,cue.at+1/30);
    return texts.join(' ').replace(/\\s+/g,' ').trim();
  }
  assert.equal(draw(),draw());
  assert.ok(draw().includes(cue.text.replace(/\\s+/g,' ').trim()));
}
""",
                str(source),
            ],
            check=True,
            capture_output=True,
        )


def test_missing_closing_evidence_does_not_call_reviewer(direct_canvas_runtime):
    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [SOURCE]
    project = author.generate(inputs)
    commands.omit_closing_frames = True
    reviewer = DirectCanvasReviewer(author._llm)
    delivery = CanvasDelivery(root, reviewer.arguments(), reviewer.run_job, commands, "test")
    with pytest.raises(AnimationUnavailable, match="scene-closing evidence"):
        delivery.deliver(project, review=True)
    assert len(provider.requests) == 1
    assert "render-final" not in commands.calls


@pytest.mark.parametrize("kind,args", [("codex", ["codex", "exec"]), ("validate", ["codex"])])
def test_offline_worker_rejects_cli_execution(tmp_path, kind, args):
    from app.courses.adapters.ai.animator import AnimationWorker

    worker = AnimationWorker(tmp_path, tmp_path, "")
    with pytest.raises(AnimationUnavailable, match="Unsupported animation worker command"):
        worker.run_job(tmp_path, kind, args, None, "retired-cli")
    assert not (tmp_path / "logs").exists()


@pytest.mark.parametrize("mismatch", ["input", "lesson", "model", "backend"])
def test_cached_direct_source_must_match_current_request(direct_canvas_runtime, mismatch):
    from dataclasses import asdict

    author, provider, _, inputs, root = direct_canvas_runtime
    provider.outputs = [SOURCE]
    project = author.generate(inputs)
    metadata = asdict(project)
    if mismatch == "input":
        metadata.update(input_hash="b" * 64, project_key="b" * 64 + "/javascript")
    elif mismatch == "lesson":
        metadata["lesson_id"] = "another-lesson"
    elif mismatch == "model":
        metadata["model"] = "another-model"
    else:
        metadata["backend"] = "codex"
    (root / ".state" / project.input_hash / "result.json").write_text(json.dumps(metadata))
    with pytest.raises(AnimationUnavailable, match="does not match this input version"):
        author.generate(inputs)
    assert len(provider.requests) == 1


def test_cached_direct_source_is_available_without_a_provider_key(direct_canvas_runtime):
    from app.courses.adapters.ai.direct_animation import DirectCanvasAnimator

    author, provider, commands, inputs, root = direct_canvas_runtime
    provider.outputs = [SOURCE]
    project = author.generate(inputs)
    offline = DirectCanvasAnimator(
        root,
        commands.tools,
        "",
        model=author._model,
        llm=author._llm,
        command_runner=commands,
    )
    assert offline.generate(inputs) == project
    assert len(provider.requests) == 1
    assert commands.calls == ["validate-0"]
