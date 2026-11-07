import hashlib
import json
from dataclasses import asdict, replace

import pytest
from fakes.canvas import RecordingDelivery
from fakes.visual_production import RecordingCompositor
from fixtures.animation import animation_inputs

from app.courses.application.generate_storyboard import artifact_hash
from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.application.storyboard_dto import storyboard_response
from app.courses.application.style_dto import StyleInput
from app.courses.application.style_resolution import resolve_style
from app.courses.domain.animation import AnimationProject
from app.courses.domain.errors import CourseError
from app.courses.domain.generation import GenerationMode
from app.courses.domain.style import LessonStyle
from app.courses.domain.visual_style import VisualStyle
from app.courses.ports.animator import (
    AnimationChangeRequest,
    AnimationUnavailable,
    StoryboardChangeRequired,
)
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.visual_production import VisualReview


@pytest.mark.parametrize("enabled,status", [(True, "approved"), (False, "skipped")])
def test_single_author_delivers_with_selected_review_policy(enabled, status):
    inputs, _, _, _ = animation_inputs()
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, review_output=enabled))
    )
    assert result.project.review_status == status
    assert len(animator.requests) == 1
    assert delivery.calls[0][1] is enabled
    assert animator.requests[0].audio == inputs.audio


def test_failed_repair_still_requires_technically_valid_original():
    inputs, _, _, _ = animation_inputs()
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [VisualReview(False, "s01: improve silhouette")] * 3
    with pytest.raises(AnimationUnavailable, match="technical validation failed"):
        ProduceCanvasAnimation(animator, delivery).execute(ProduceCanvasAnimationRequest(inputs))
    assert len(animator.requests) == 2
    assert animator.requests[1].visual_feedback == "s01: improve silhouette"
    assert animator.requests[1].previous_project_key
    assert all(
        r.audio == inputs.audio and r.alignment == inputs.alignment for r in animator.requests
    )
    assert [review for _, review in delivery.calls] == [True, False, False]
    assert delivery.repair_feedback == [None, "s01: improve silhouette", None]
    assert delivery.calls[2][0] == delivery.calls[0][0]


@pytest.mark.parametrize(
    "failure",
    [
        AnimationUnavailable("Repair worker unavailable"),
        StoryboardChangeRequired(
            AnimationChangeRequest(("s01",), "Missing sourced map data", "Provide geographic data")
        ),
    ],
)
def test_optional_repair_failure_warns_and_delivers_original(failure, caplog):
    inputs, _, _, _ = animation_inputs()
    published = []
    animator = RecordingCompositor([], repair_error=failure)
    delivery = RecordingDelivery()
    delivery.decisions = [VisualReview(False, "Improve map labels"), VisualReview(True, "Decoded")]
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, source_ready=published.append))
    )
    assert result.project.review_status == "warning"
    assert result.project.project_key == delivery.calls[0][0].project_key
    assert len(published) == 1
    assert published[-1].project_key == result.project.project_key
    assert delivery.calls[1][0] == delivery.calls[0][0]
    assert [review for _, review in delivery.calls] == [True, False]
    assert delivery.repair_feedback == [None, None]
    assert len(animator.requests) == 2
    assert animator.requests[1].audio == inputs.audio
    assert "non-blocking" in caplog.text
    assert str(failure) in caplog.text


def test_unavailable_reviewer_warns_and_still_renders(caplog):
    inputs, _, _, _ = animation_inputs()
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [
        AnimationUnavailable("Invalid review report"),
        VisualReview(True, "Decoded"),
    ]
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(inputs)
    )
    assert result.project.review_status == "warning"
    assert len(animator.requests) == 1
    assert [review for _, review in delivery.calls] == [True, False]
    assert "Invalid review report" in caplog.text


def test_invalid_repaired_video_falls_back_to_original(caplog):
    inputs, _, _, _ = animation_inputs()
    published = []
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [
        VisualReview(False, "Enlarge labels"),
        AnimationUnavailable("Repaired video cannot be decoded"),
        VisualReview(True, "Original decoded"),
    ]
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, source_ready=published.append))
    )
    assert result.project.review_status == "warning"
    assert result.project.project_key == delivery.calls[0][0].project_key
    assert delivery.calls[1][0].project_key != result.project.project_key
    assert published[-1].project_key == result.project.project_key
    assert [review for _, review in delivery.calls] == [True, False, False]
    assert "cannot be decoded" in caplog.text


def test_original_encoder_failure_is_not_hidden_by_advisory_review():
    inputs, _, _, _ = animation_inputs()
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [
        AnimationUnavailable("Reviewer unavailable"),
        AnimationUnavailable("Encoder failed"),
    ]
    with pytest.raises(AnimationUnavailable, match="Encoder failed"):
        ProduceCanvasAnimation(animator, delivery).execute(ProduceCanvasAnimationRequest(inputs))


def test_disabled_review_never_launches_a_repair_on_technical_failure():
    inputs, _, _, _ = animation_inputs()
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [VisualReview(False, "Video could not be decoded")]
    with pytest.raises(AnimationUnavailable, match="technical validation failed"):
        ProduceCanvasAnimation(animator, delivery).execute(
            ProduceCanvasAnimationRequest(replace(inputs, review_output=False))
        )
    assert len(animator.requests) == 1
    assert [review for _, review in delivery.calls] == [False]


def test_review_policy_change_preserves_narration_and_script():
    _, course, _, _ = animation_inputs()
    lesson = course.chapters[0].lessons[0]
    previous = LessonStyle()
    updated = replace(lesson, style=previous).restyle(replace(previous, review_output=False))
    assert updated.alignment == lesson.alignment
    assert updated.storyboard == lesson.storyboard
    assert updated.plan == lesson.plan
    assert updated.animation is None


@pytest.mark.parametrize(
    "identity,version",
    [
        ("unknown", 1),
        ("flat-vector-science", 2),
        ("watercolor-wash", 2),
        ("tech-glow", 2),
        ("whiteboard", 2),
        ("halftone-pop", 2),
        ("risograph", 2),
        ("gouache-poster", 2),
        ("soft-3d", 2),
        ("memphis", 2),
        ("bauhaus", 2),
        ("swiss-grid", 2),
    ],
)
def test_unknown_style_package_is_rejected(identity, version):
    with pytest.raises(CourseError, match="Choose"):
        VisualStyle(identity, version)


def test_style_direction_names_executable_reference():
    assert "Flat-Vector Science v1" in LessonStyle().visual_direction()


def test_empty_continuity_fields_preserve_legacy_audio_identity():
    legacy = {"scene_id": "s01", "narration_text": "Explain trade"}
    extended = {
        **legacy,
        "object_ids": (),
        "camera": "",
        "opening_composition": "",
        "closing_composition": "",
        "continuity_from_previous": "",
    }
    original = hashlib.sha256(
        json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert artifact_hash(extended) == original
    assert artifact_hash({**extended, "camera": "Pull back"}) != original


def test_review_only_edit_works_without_voice_or_style_provider_and_preserves_narrator():
    previous = LessonStyle(voice_id="configured-narrator", voice_name="Saved narrator")
    updated = resolve_style(
        "History", StyleInput(review_output=False), GenerationMode.FAST, None, None, previous
    )
    assert updated is not None
    assert updated.voice_id == previous.voice_id
    assert updated.delivery == previous.delivery
    assert updated.review_output is False
    assert updated.version == previous.version + 1


def test_review_policy_reuses_latest_repaired_source_without_another_author_call():
    inputs, course, _, _ = animation_inputs()
    source = AnimationProject(
        inputs.plan.lesson_id,
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "fast-model",
        inputs.alignment.duration_sec,
        backend="direct",
        review_status="approved",
    )
    original = replace(course.chapters[0].lessons[0], style=LessonStyle(), animation=source)
    edited = original.restyle(replace(original.style, review_output=False))
    assert edited.review_source(edited.style) == source
    # Multiple preference edits before regenerating still retain the actual final artwork.
    edited = edited.restyle(replace(edited.style, review_output=True))
    assert edited.review_source(edited.style) == source
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, existing_project=source, review_output=False))
    )
    assert animator.requests == []
    assert result.project.project_key == source.project_key
    assert result.project.review_status == "skipped"


@pytest.mark.parametrize("model,author_calls", [(AnimatorModel.LUNA, 0), (AnimatorModel.SOL, 1)])
def test_explicit_model_change_does_not_reuse_another_models_artwork(model, author_calls):
    inputs, _, _, _ = animation_inputs()
    source = AnimationProject(
        inputs.plan.lesson_id,
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        AnimatorModel.LUNA.value,
        inputs.alignment.duration_sec,
        backend="direct",
    )
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(
            replace(inputs, existing_project=source, animator_model=model, review_output=False)
        )
    )
    assert len(animator.requests) == author_calls
    if author_calls:
        assert animator.requests[0].animator_model == model
        assert animator.requests[0].existing_project is None


def test_existing_source_can_receive_a_bounded_visual_repair():
    inputs, _, _, _ = animation_inputs()
    source = AnimationProject(
        inputs.plan.lesson_id,
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "fast-model",
        inputs.alignment.duration_sec,
        backend="direct",
    )
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [
        VisualReview(False, "Enlarge the main illustration"),
        VisualReview(True, "Clear"),
    ]
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, existing_project=source))
    )
    assert len(animator.requests) == 1
    assert animator.requests[0].existing_project is None
    assert animator.requests[0].previous_project_key == source.project_key
    assert result.project.review_status == "repaired"
    assert [review for _, review in delivery.calls] == [True, False]
    assert delivery.repair_feedback[-1] == "Enlarge the main illustration"


def test_public_storyboard_preserves_all_visual_continuity_fields():
    inputs, _, _, _ = animation_inputs()
    board = replace(
        inputs.storyboard,
        scenes=tuple(
            replace(
                s,
                object_ids=("network", "caravan"),
                opening_composition="Wide network",
                closing_composition="Goods reach the oasis",
                camera="Follow the caravan",
                continuity_from_previous="Keep the network in place",
            )
            for s in inputs.storyboard.scenes
        ),
    )
    public = storyboard_response(board)
    assert public is not None
    assert asdict(public) == asdict(board)


@pytest.mark.parametrize("original,selected", [("codex", "direct")])
def test_engine_switch_does_not_reuse_other_agents_artwork(original, selected):
    from app.courses.ports.animation_backend import AnimationBackend

    inputs, _, _, _ = animation_inputs()
    source = AnimationProject(
        inputs.plan.lesson_id,
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "model",
        inputs.alignment.duration_sec,
        backend=original,
    )
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(
            replace(inputs, existing_project=source, animation_backend=AnimationBackend(selected))
        )
    )
    assert len(animator.requests) == 1
    assert animator.requests[0].existing_project is None
    assert animator.requests[0].animation_backend.value == selected


@pytest.mark.parametrize("repair", [False, True])
def test_only_reviewed_or_repaired_source_is_announced(repair):
    inputs, _, _, _ = animation_inputs()
    published = []

    def observe_delivery(project):
        assert published == []

    animator, delivery = RecordingCompositor([]), RecordingDelivery(observe_delivery)
    delivery.decisions = (
        [VisualReview(False, "Enlarge labels"), VisualReview(True, "Valid")]
        if repair
        else [VisualReview(True, "Valid")]
    )
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(replace(inputs, source_ready=published.append))
    )
    assert len(published) == 1
    assert all(project.review_status == "pending" for project in published)
    assert published[0].project_key == result.project.project_key
    assert result.project.review_status == ("repaired" if repair else "approved")


def test_watercolor_direction_and_visual_change_scope():
    previous = LessonStyle()
    updated = replace(previous, visual_style_id="watercolor-wash")
    assert "Watercolor Wash v1" in updated.visual_direction()
    assert "cold-press" in updated.visual_direction()
    assert "Flat-Vector" not in updated.visual_direction()
    assert updated.change_scope(previous) == "visuals"
    assert updated.change_scope(updated) == "none"


def test_tech_glow_direction_and_visual_change_scope():
    previous = LessonStyle()
    updated = replace(previous, visual_style_id="tech-glow")
    assert "Tech Glow Explainer v1" in updated.visual_direction()
    assert "bloom" in updated.visual_direction()
    assert "Watercolor" not in updated.visual_direction()
    assert updated.change_scope(previous) == "visuals"
    assert updated.change_scope(updated) == "none"


def test_whiteboard_direction_and_visual_change_scope():
    previous = LessonStyle()
    updated = replace(previous, visual_style_id="whiteboard")
    assert "Whiteboard Explainer v1" in updated.visual_direction()
    assert "dry-erase" in updated.visual_direction()
    assert "Tech Glow" not in updated.visual_direction()
    assert updated.change_scope(previous) == "visuals"
    assert updated.change_scope(updated) == "none"


def test_halftone_direction_and_visual_change_scope():
    previous = LessonStyle()
    updated = replace(previous, visual_style_id="halftone-pop")
    assert "Halftone Pop Panel v1" in updated.visual_direction()
    assert "Ben-Day" in updated.visual_direction()
    assert "Whiteboard" not in updated.visual_direction()
    assert updated.change_scope(previous) == "visuals"
    assert updated.change_scope(updated) == "none"


@pytest.mark.parametrize("job_id", [None, "original-job", "another-job"])
def test_cached_source_only_resumes_the_animator_session_within_its_job(job_id):
    from app.courses.ports.agent_sessions import AgentSessionContext

    inputs, _, _, _ = animation_inputs()
    source = AnimationProject(
        inputs.plan.lesson_id,
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "test",
        inputs.alignment.duration_sec,
        backend="direct",
        session_id="agent_original",
        owner_id="owner",
        job_id="original-job",
    )
    animator, delivery = RecordingCompositor([]), RecordingDelivery()
    delivery.decisions = [VisualReview(False, "Enlarge labels"), VisualReview(True, "Valid")]
    drafts = []
    ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(
            replace(
                inputs,
                existing_project=source,
                session=AgentSessionContext("owner", inputs.plan.lesson_id, job_id),
                source_ready=drafts.append,
            )
        )
    )
    expected_session = None if job_id == "another-job" else "agent_original"
    assert animator.requests[0].session.session_id == expected_session
    assert delivery.calls[0][0].session_id == expected_session
    assert len(drafts) == 1
    assert drafts[0].project_key == delivery.calls[1][0].project_key


@pytest.mark.parametrize(
    "style_id,name,medium",
    [
        ("risograph", "Risograph Zine", "spot inks"),
        ("gouache-poster", "Gouache Travel Poster", "opaque matte"),
        ("soft-3d", "Soft 3D Clay", "rounded extrusions"),
        ("memphis", "Memphis Group", "hard offset shadows"),
        ("bauhaus", "Bauhaus Poster", "lithographic"),
        ("swiss-grid", "International Typographic Style", "12-column"),
    ],
)
def test_uploaded_style_changes_visuals_without_changing_teaching_or_voice(style_id, name, medium):
    previous = LessonStyle()
    updated = replace(previous, visual_style_id=style_id)
    assert name + " v1" in updated.visual_direction()
    assert medium in updated.visual_direction()
    assert updated.change_scope(previous) == "visuals"
    assert updated.change_scope(updated) == "none"
