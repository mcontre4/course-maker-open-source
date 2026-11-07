from dataclasses import replace

import pytest
from fixtures.syllabus import COURSE_ID, LESSON_ID

from app.courses.application.generate_storyboard import GenerateStoryboardRequest
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.ports.storyboard_agent import StoryboardGenerationUnavailable


def test_saves_versioned_storyboard_and_reuses_without_another_call(storyboard_generation):
    service, courses, agent, uow, before, _ = storyboard_generation
    request = GenerateStoryboardRequest(COURSE_ID, LESSON_ID, "High contrast diagrams")
    result = service.execute(request)
    saved = courses.require_by_id(before.id).lesson(LESSON_ID)
    assert saved.storyboard.lesson_id == LESSON_ID
    assert saved.storyboard_generation.status == "storyboard_ready"
    assert len(saved.storyboard_generation.input_hash) == 64
    assert len(saved.storyboard_generation.output_hash) == 64
    assert saved.storyboard_generation.usage.model == "test-model"
    assert saved.video_url is None
    assert result.chapters[0].lessons[0].storyboard.lesson_id == LESSON_ID
    calls = len(agent.calls)
    assert service.execute(request) == result
    assert service.execute(GenerateStoryboardRequest(COURSE_ID, LESSON_ID)) == result
    assert len(agent.calls) == calls
    assert uow.commits == 1
    with pytest.raises(CourseConflict, match="different visual"):
        service.execute(replace(request, visual_style="Different"))


@pytest.mark.parametrize("change", ["draft", "plan", "guide", "reviewed", "lesson"])
def test_preconditions_prevent_provider_spend(storyboard_generation, change):
    service, courses, agent, _, before, conversations = storyboard_generation
    request = GenerateStoryboardRequest(COURSE_ID, LESSON_ID)
    if change == "draft":
        courses.save(replace(before, status="draft"))
    elif change == "plan":
        courses.save(before._replace_lesson(replace(before.lesson(LESSON_ID), plan=None)))
    elif change == "guide":
        conversations.items.clear()
    elif change == "reviewed":
        courses.save(replace(before, reviewed=(LESSON_ID,)))
    else:
        request = replace(request, lesson_id="lesson_00000000-0000-0000-0000-000000000099")
    with pytest.raises((CourseConflict, CourseNotFound)):
        service.execute(request)
    assert not agent.calls


def test_provider_failure_keeps_plan_and_content(storyboard_generation):
    service, courses, agent, uow, before, _ = storyboard_generation
    agent.error = StoryboardGenerationUnavailable("Unavailable")
    with pytest.raises(StoryboardGenerationUnavailable):
        service.execute(GenerateStoryboardRequest(COURSE_ID, LESSON_ID))
    assert courses.require_by_id(before.id) == before
    assert not uow.commits


@pytest.mark.parametrize("change", ["course", "guide"])
def test_concurrent_change_cannot_be_overwritten(storyboard_generation, change):
    service, courses, agent, uow, before, conversations = storyboard_generation
    if change == "course":
        agent.during_run = lambda: courses.save(replace(before, title="Changed"))
    else:
        agent.during_run = lambda: conversations.items.clear()
    with pytest.raises(CourseConflict, match="changed"):
        service.execute(GenerateStoryboardRequest(COURSE_ID, LESSON_ID))
    assert courses.require_by_id(before.id).lesson(LESSON_ID).storyboard is None
    assert not uow.commits


def test_invalid_provider_result_is_not_saved(storyboard_generation):
    from fixtures.storyboard import storyboard

    service, courses, agent, uow, before, _ = storyboard_generation
    agent.output = replace(storyboard(before.lesson(LESSON_ID).plan), lesson_id="wrong")
    with pytest.raises(CourseError, match="Preserve"):
        service.execute(GenerateStoryboardRequest(COURSE_ID, LESSON_ID))
    assert courses.require_by_id(before.id) == before
    assert not uow.commits


def test_outline_and_plan_changes_invalidate_storyboard(storyboard_generation):
    service, courses, _, _, before, _ = storyboard_generation
    service.execute(GenerateStoryboardRequest(COURSE_ID, LESSON_ID))
    course = courses.require_by_id(before.id)
    lesson = course.lesson(LESSON_ID)
    assert lesson.revise_outline("Changed", lesson.topics, lesson.minutes).storyboard is None
    assert lesson.revise_outline(lesson.title, lesson.topics, lesson.minutes).storyboard is not None
    updated = course.plan_lesson(LESSON_ID, lesson.plan, lesson.plan_generation)
    assert updated.lesson(LESSON_ID).storyboard is None
    assert updated.lesson(LESSON_ID).storyboard_generation is None
