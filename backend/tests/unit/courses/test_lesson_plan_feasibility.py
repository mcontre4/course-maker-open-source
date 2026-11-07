from dataclasses import replace

import pytest
from fixtures.lesson_plan import infeasible_lesson_plan, lesson_plan

from app.courses.domain.errors import CourseConflict, CourseError


@pytest.mark.parametrize("offset", [-1, 1, 30])
def test_assessed_feasible_plan_requires_exact_timing(planned_course, offset):
    _, curriculum = planned_course
    brief = curriculum.chapters[0].lessons[0]
    plan = lesson_plan(brief)
    plan = replace(plan, beats=(replace(plan.beats[0], seconds=brief.video_minutes * 60 + offset),))
    with pytest.raises(CourseError, match="exactly"):
        plan.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)


def test_legacy_plan_preserves_previously_valid_timing(planned_course):
    _, curriculum = planned_course
    brief = curriculum.chapters[0].lessons[0]
    plan = lesson_plan(brief)
    legacy = replace(
        plan,
        feasibility_status=None,
        beats=(replace(plan.beats[0], seconds=brief.video_minutes * 60 + 30),),
    )
    legacy.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)
    legacy.require_feasible()


@pytest.mark.parametrize("scope_recommendation", [True, False])
def test_infeasible_plan_preserves_coverage_and_explains_the_conflict(
    planned_course, scope_recommendation
):
    _, curriculum = planned_course
    brief = curriculum.chapters[0].lessons[0]
    plan = infeasible_lesson_plan(brief)
    if not scope_recommendation:
        plan = replace(plan, recommended_scope_adjustment="")
    plan.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)
    with pytest.raises(CourseConflict, match="two more minutes") as error:
        plan.require_feasible()
    assert f"{brief.video_minutes + 2} video minutes" in str(error.value)
    if scope_recommendation:
        assert plan.recommended_scope_adjustment in str(error.value)
    else:
        assert "Suggested scope adjustment" not in str(error.value)


@pytest.mark.parametrize("change", ["fits", "short_recommendation", "coverage", "objectives"])
def test_infeasibility_does_not_bypass_coverage_or_consistent_estimates(planned_course, change):
    _, curriculum = planned_course
    brief = curriculum.chapters[0].lessons[0]
    plan = infeasible_lesson_plan(brief)
    if change == "fits":
        plan = replace(plan, beats=(replace(plan.beats[0], seconds=brief.video_minutes * 60),))
    elif change == "short_recommendation":
        plan = replace(plan, recommended_video_minutes=brief.video_minutes + 1)
    elif change == "coverage":
        plan = replace(plan, beats=(replace(plan.beats[0], concepts=("Other",)),))
    else:
        plan = replace(plan, objectives=("Different objective",))
    with pytest.raises(CourseError):
        plan.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)


@pytest.mark.parametrize(
    "change",
    [
        {"feasibility_explanation": ""},
        {"recommended_video_minutes": None},
        {"recommended_video_minutes": None, "recommended_scope_adjustment": ""},
        {"recommended_video_minutes": True},
        {"recommended_video_minutes": 0},
        {"recommended_video_minutes": -1},
        {"recommended_video_minutes": 12.5},
        {"recommended_video_minutes": 1441},
        {"feasibility_status": "unknown"},
        {"feasibility_status": "feasible"},
    ],
)
def test_infeasible_plan_requires_a_valid_explanation_and_recommendation(planned_course, change):
    _, curriculum = planned_course
    plan = infeasible_lesson_plan(curriculum.chapters[0].lessons[0])
    with pytest.raises(CourseError):
        replace(plan, **change)


def test_primary_example_can_be_a_case_without_solution_steps(planned_course):
    _, curriculum = planned_course
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    example = replace(
        plan.examples[0],
        problem="Two colleagues interpret the same message differently.",
        steps=(),
        result="Context changes how a message is understood.",
    )
    assert replace(plan, examples=(example,)).examples == (example,)


@pytest.mark.parametrize("missing", ["check_question", "expected_answer"])
def test_diagnostic_question_and_answer_must_be_paired(planned_course, missing):
    _, curriculum = planned_course
    beat = lesson_plan(curriculum.chapters[0].lessons[0]).beats[0]
    with pytest.raises(CourseError, match="both"):
        replace(beat, **{missing: ""})


def test_feasible_plan_has_no_infeasibility_recommendations(planned_course):
    _, curriculum = planned_course
    brief = curriculum.chapters[0].lessons[0]
    plan = lesson_plan(brief)
    plan.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)
    assert plan.recommended_video_minutes is None
    assert plan.feasibility_explanation == ""
    assert plan.recommended_scope_adjustment == ""


@pytest.mark.parametrize(
    "change",
    [
        {"recommended_video_minutes": 12},
        {"feasibility_explanation": "Needs more time"},
        {"recommended_scope_adjustment": "Remove an objective"},
    ],
)
def test_feasible_plan_rejects_infeasibility_fields(planned_course, change):
    _, curriculum = planned_course
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    with pytest.raises(CourseError, match="Only infeasible"):
        replace(plan, **change)
