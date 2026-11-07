from dataclasses import replace

import pytest
from fixtures.lesson_plan import lesson_plan
from fixtures.syllabus import COURSE_ID, LESSON_ID, make_planned_course

from app.courses.application.generate_lesson import GenerateLessonRequest
from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.ports.lesson_agent import LessonGenerationUnavailable


def test_generates_saves_and_reuses_plan(lesson_generation):
    service, courses, agent, uow, before = lesson_generation
    response = service.execute(GenerateLessonRequest(COURSE_ID, LESSON_ID))
    saved = courses.require_by_id(before.id)
    assert saved.lesson(LESSON_ID).plan is not None
    assert saved.lesson(LESSON_ID).video_url is None
    assert response.chapters[0].lessons[0].plan.objectives == ("Assign a value",)
    assert agent.calls[0].guide.teaching_level == "beginner"
    assert agent.calls[0].chapter.title == "Basics"
    assert agent.calls[0].previous_lesson is None
    assert service.execute(GenerateLessonRequest(COURSE_ID)) == response
    assert len(agent.calls) == uow.commits == 1


def test_rejects_draft_before_provider(lesson_generation):
    service, courses, agent, _, before = lesson_generation
    courses.save(replace(before, status="draft"))
    with pytest.raises(CourseConflict, match="Approve"):
        service.execute(GenerateLessonRequest(COURSE_ID))
    assert not agent.calls


def test_provider_failure_preserves_course(lesson_generation):
    service, courses, agent, uow, before = lesson_generation
    agent.error = LessonGenerationUnavailable("Unavailable")
    with pytest.raises(LessonGenerationUnavailable):
        service.execute(GenerateLessonRequest(COURSE_ID))
    assert courses.require_by_id(before.id) == before
    assert uow.commits == 0


def test_concurrent_edit_cannot_be_overwritten(lesson_generation):
    service, courses, agent, uow, before = lesson_generation
    agent.during_run = lambda: courses.save(replace(before, title="Changed"))
    with pytest.raises(CourseConflict, match="changed"):
        service.execute(GenerateLessonRequest(COURSE_ID))
    assert courses.require_by_id(before.id).title == "Changed"
    assert uow.commits == 0


@pytest.mark.parametrize("change", ["id", "objective", "coverage", "timing"])
def test_plan_must_preserve_the_brief(change):
    _, curriculum = make_planned_course()
    brief = curriculum.chapters[0].lessons[0]
    plan = lesson_plan(brief)
    if change == "id":
        plan = replace(plan, lesson_id="wrong")
    elif change == "objective":
        plan = replace(plan, objectives=("Wrong",))
    elif change == "coverage":
        plan = replace(plan, beats=(replace(plan.beats[0], concepts=("Other",)),))
    else:
        plan = replace(plan, beats=(replace(plan.beats[0], seconds=60),))
    with pytest.raises(CourseError):
        plan.validate_brief(brief.lesson_id, brief.objectives, brief.concepts, brief.video_minutes)


def test_reviewed_lesson_rejected_before_model_execution(lesson_generation):
    service, courses, agent, uow, before = lesson_generation
    courses.save(replace(before, reviewed=(LESSON_ID,)))
    with pytest.raises(CourseConflict, match="reviewed"):
        service.execute(GenerateLessonRequest(COURSE_ID))
    assert not agent.calls
    assert uow.commits == 0


def test_direct_domain_updates_cannot_attach_another_lessons_plan():
    from app.courses.domain.lesson_plan import PlanGeneration

    course, curriculum = make_planned_course()
    plan = replace(lesson_plan(curriculum.chapters[0].lessons[0]), lesson_id="another")
    with pytest.raises(CourseError, match="belong"):
        course.approve().plan_lesson(LESSON_ID, plan, PlanGeneration("test", 1, 1, 10))


def test_lesson_enforces_plan_coverage_even_outside_the_use_case():
    course, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    lesson = course.lesson(LESSON_ID)
    with pytest.raises(CourseError, match="Every syllabus concept"):
        replace(lesson, plan=replace(plan, beats=(replace(plan.beats[0], concepts=("Other",)),)))


def test_infeasible_plan_is_saved_but_cannot_reach_the_scripting_agent(storyboard_generation):
    from fixtures.lesson_plan import infeasible_lesson_plan

    from app.courses.application.generate_storyboard import GenerateStoryboardRequest
    from app.courses.domain.lesson_plan import PlanGeneration

    service, courses, agent, _, before, conversations = storyboard_generation
    brief = conversations.get_by_course_id(before.id).curriculum.chapters[0].lessons[0]
    plan = infeasible_lesson_plan(brief)
    courses.save(before.plan_lesson(LESSON_ID, plan, PlanGeneration("test", 1, 0, 100)))
    with pytest.raises(CourseConflict, match="scope needs review"):
        service.execute(GenerateStoryboardRequest(COURSE_ID, LESSON_ID))
    saved = courses.require_by_id(before.id)
    assert saved.lesson(LESSON_ID).plan == plan
    assert saved.lesson(LESSON_ID).minutes == before.lesson(LESSON_ID).minutes
    assert saved.lesson(LESSON_ID).storyboard is None
    assert not agent.calls
