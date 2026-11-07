from dataclasses import replace

import pytest
from fixtures.syllabus import LESSON_ID

from app.courses.application.generate_animation import GenerateAnimationRequest
from app.courses.domain.errors import CourseConflict
from app.courses.ports.animator import (
    AnimationChangeRequest,
    AnimationUnavailable,
    StoryboardChangeRequired,
)
from app.courses.ports.animator_model import AnimatorModel


def test_saves_animation_without_changing_upstream_content(animation_generation):
    service, courses, agent, artifacts, uow, before = animation_generation
    response = service.execute(
        GenerateAnimationRequest(str(before.id), LESSON_ID, "Readable diagrams")
    )
    saved = courses.require_by_id(before.id).lesson(LESSON_ID)
    original = before.lesson(LESSON_ID)
    assert saved.animation.status == "animation_ready"
    assert (saved.plan, saved.storyboard, saved.alignment) == (
        original.plan,
        original.storyboard,
        original.alignment,
    )
    assert response.chapters[0].lessons[0].animation.input_hash == "a" * 64
    assert len(agent.calls[0].audio) == len(original.alignment.scenes)
    assert saved.video_url is None
    assert uow.commits == 1


@pytest.mark.parametrize("missing", ["plan", "storyboard", "alignment"])
def test_missing_prerequisites_prevent_codex_calls(animation_generation, missing):
    service, courses, agent, _, _, before = animation_generation
    changes = {"alignment": None}
    if missing in {"plan", "storyboard"}:
        changes["storyboard"] = None
    if missing == "plan":
        changes["plan"] = None
    courses.save(before._replace_lesson(replace(before.lesson(LESSON_ID), **changes)))
    with pytest.raises(CourseConflict):
        service.execute(GenerateAnimationRequest(str(before.id), LESSON_ID, "Readable diagrams"))
    assert not agent.calls


def test_missing_audio_prevents_codex_calls(animation_generation):
    service, _, agent, artifacts, _, before = animation_generation
    artifacts.objects.clear()
    with pytest.raises(AnimationUnavailable):
        service.execute(GenerateAnimationRequest(str(before.id), LESSON_ID, "Readable diagrams"))
    assert not agent.calls


def test_upstream_edits_reject_stale_animation(animation_generation):
    service, courses, agent, _, _, before = animation_generation
    agent.on_generate = lambda: courses.save(replace(before, title="Edited during generation"))
    with pytest.raises(CourseConflict):
        service.execute(GenerateAnimationRequest(str(before.id), LESSON_ID, "Readable diagrams"))
    assert courses.require_by_id(before.id).lesson(LESSON_ID).animation is None


@pytest.mark.parametrize(
    "error",
    [
        AnimationUnavailable("worker failure"),
        StoryboardChangeRequired(
            AnimationChangeRequest(("s01",), "Cannot draw", "Provide source data")
        ),
    ],
)
def test_failures_do_not_mark_animation_ready(animation_generation, error):
    service, courses, agent, _, uow, before = animation_generation
    agent.error = error
    with pytest.raises(type(error)):
        service.execute(GenerateAnimationRequest(str(before.id), LESSON_ID, "Readable diagrams"))
    assert courses.require_by_id(before.id) == before
    assert uow.commits == 0


def test_plan_replacement_invalidates_animation(animation_generation):
    service, courses, _, _, _, before = animation_generation
    service.execute(GenerateAnimationRequest(str(before.id), LESSON_ID, "Readable diagrams"))
    saved = courses.require_by_id(before.id)
    lesson = saved.lesson(LESSON_ID)
    updated = saved.plan_lesson(LESSON_ID, lesson.plan, lesson.plan_generation)
    assert updated.lesson(LESSON_ID).animation is None


@pytest.mark.parametrize("model", [None, *AnimatorModel])
def test_animator_choice_reaches_assembly_without_changing_saved_inputs(
    animation_generation, model
):
    service, courses, agent, _, _, before = animation_generation
    service.execute(
        GenerateAnimationRequest(
            str(before.id), LESSON_ID, "Readable diagrams", animator_model=model
        )
    )
    assert agent.calls[0].animator_model == model
    saved = courses.require_by_id(before.id).lesson(LESSON_ID)
    assert saved.animation is not None
    assert saved.storyboard == before.lesson(LESSON_ID).storyboard
