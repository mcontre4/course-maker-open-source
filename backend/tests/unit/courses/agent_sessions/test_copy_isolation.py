from dataclasses import replace

from fixtures.animation import animation_inputs

from app.courses.domain.animation import AnimationProject
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.storyboard import StoryboardGeneration


def test_copy_does_not_inherit_producer_sessions():
    inputs, course, _, _ = animation_inputs()
    generation = PlanGeneration("test", 1, 0, 1, "agent_original")
    source = replace(
        course.lesson(inputs.plan.lesson_id),
        plan_generation=generation,
        storyboard_generation=StoryboardGeneration(
            generation,
            "a" * 64,
            "b" * 64,
            "test",
            None,
            script_session_id="agent_script",
        ),
        animation=AnimationProject(
            inputs.plan.lesson_id,
            "a" * 64,
            "a" * 64 + "/javascript",
            "b" * 64,
            "test",
            inputs.alignment.duration_sec,
            session_id="agent_animator",
            reviewer_session_id="agent_reviewer",
            owner_id="original-user",
            job_id="original-job",
        ),
    )
    copied = source.copy(LessonId("lesson_00000000-0000-0000-0000-000000000099"))
    assert copied.plan_generation.session_id is None
    assert copied.storyboard_generation.script_session_id is None
    assert copied.storyboard_generation.usage.session_id is None
    assert copied.animation.session_id is None and copied.animation.reviewer_session_id is None
    assert copied.animation.owner_id is None and copied.animation.job_id is None
    assert source.animation.session_id == "agent_animator"
