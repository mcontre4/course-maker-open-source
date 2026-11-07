from dataclasses import replace

import pytest
from fixtures.lesson_plan import infeasible_lesson_plan
from fixtures.outline import outline_input

from app.courses.application.outline_dto import SaveStandaloneOutlineRequest
from app.courses.application.save_standalone_outline import SaveStandaloneOutline
from app.courses.application.standalone import ApproveStandaloneLesson
from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.identifiers import LessonId

OWNER = "user_00000000-0000-0000-0000-000000000001"


def test_infeasible_outline_is_saved_without_changing_the_requested_duration(standalone):
    repo, uow, agent, planner, created = standalone
    before = repo.require_by_id(LessonId(created.id))
    plan = infeasible_lesson_plan(before.brief())
    # A recommendation may exceed the standalone product limit; it is not a video target.
    plan = replace(plan, beats=(replace(plan.beats[0], seconds=720),), recommended_video_minutes=12)
    agent.plan = plan
    response = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.plan == plan
    assert saved.content.minutes == before.content.minutes
    assert saved.content.topics == before.content.topics
    assert not saved.approved
    assert response.content.plan.feasibility_status == "infeasible"
    assert response.content.plan.recommended_video_minutes == 12
    with pytest.raises(CourseConflict, match="scope needs review"):
        ApproveStandaloneLesson(repo, uow).execute(
            ReviseStandaloneLessonRequest(created.id, OWNER, response.revision)
        )
    assert repo.require_by_id(LessonId(created.id)) == saved

    outline = outline_input(response.content.plan)
    edited = SaveStandaloneOutline(repo, uow).execute(
        SaveStandaloneOutlineRequest(
            created.id,
            OWNER,
            response.revision,
            replace(outline, required_facts=("Keep the essential relationship explicit",)),
        )
    )
    persisted = repo.require_by_id(LessonId(created.id))
    assert edited.content.plan.feasibility_status == "infeasible"
    assert persisted.content.plan.recommended_video_minutes == 12
    assert persisted.content.plan.feasibility_explanation == plan.feasibility_explanation
    assert persisted.content.plan.recommended_scope_adjustment == plan.recommended_scope_adjustment


@pytest.mark.parametrize("status", ["feasible", "infeasible"])
def test_legacy_outline_edit_preserves_an_existing_assessment(standalone, status):
    repo, uow, agent, planner, created = standalone
    if status == "infeasible":
        agent.plan = infeasible_lesson_plan(repo.require_by_id(LessonId(created.id)).brief())
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    outline = replace(
        outline_input(planned.content.plan),
        feasibility_status=None,
        feasibility_explanation="",
        recommended_video_minutes=None,
        recommended_scope_adjustment="",
        required_facts=("Keep the required relationship explicit",),
    )
    SaveStandaloneOutline(repo, uow).execute(
        SaveStandaloneOutlineRequest(created.id, OWNER, planned.revision, outline)
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.plan.feasibility_status == status
    assert (
        saved.content.plan.feasibility_explanation == planned.content.plan.feasibility_explanation
    )
    assert (
        saved.content.plan.recommended_video_minutes
        == planned.content.plan.recommended_video_minutes
    )


def test_omitting_assessment_cannot_relax_the_exact_timing_requirement(standalone):
    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    before = repo.require_by_id(LessonId(created.id))
    outline = outline_input(planned.content.plan)
    outline = replace(
        outline,
        feasibility_status=None,
        beats=(replace(outline.beats[0], seconds=179),),
    )
    with pytest.raises(CourseError, match="exactly"):
        SaveStandaloneOutline(repo, uow).execute(
            SaveStandaloneOutlineRequest(created.id, OWNER, planned.revision, outline)
        )
    assert repo.require_by_id(LessonId(created.id)) == before


@pytest.mark.parametrize(("seconds", "recommended"), [(181, 4), (361, 7)])
def test_timing_edits_refresh_the_infeasible_duration_recommendation(
    standalone, seconds, recommended
):
    repo, uow, agent, planner, created = standalone
    agent.plan = infeasible_lesson_plan(repo.require_by_id(LessonId(created.id)).brief())
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    outline = outline_input(planned.content.plan)
    outline = replace(outline, beats=(replace(outline.beats[0], seconds=seconds),))
    result = SaveStandaloneOutline(repo, uow).execute(
        SaveStandaloneOutlineRequest(created.id, OWNER, planned.revision, outline)
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.plan.recommended_video_minutes == recommended
    assert result.content.plan.recommended_video_minutes == recommended
    assert saved.content.plan.feasibility_status == "infeasible"
    assert saved.content.plan.beats[0].seconds == seconds
    assert saved.content.minutes == 3
    assert not saved.approved
