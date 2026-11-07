from dataclasses import replace

import pytest
from fakes.courses import InMemoryCourses, RecordingUnitOfWork, SequenceIds
from fixtures.public_content import finished_course

from app.courses.application.copy_lesson import CopyLesson, CopyLessonRequest
from app.courses.application.save_standalone_script import (
    SaveStandaloneScript,
    SaveStandaloneScriptRequest,
)
from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
from app.courses.domain.errors import CourseError, CourseNotFound
from app.courses.domain.identifiers import LessonId
from app.courses.domain.interactive import LessonInteractive, lesson_plan_hash

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"


def copy_service(repo, courses=None):
    ids = SequenceIds()
    ids.new_uuid()
    return CopyLesson(repo, courses or InMemoryCourses(), RecordingUnitOfWork(repo), ids)


def test_owner_copies_empty_draft_then_generates_its_own_outline(standalone):
    repo, _, _, planner, created = standalone
    copied = copy_service(repo).execute(CopyLessonRequest(created.id, OWNER))
    assert copied.id != created.id
    assert copied.owner_id == OWNER
    assert copied.content.title == "Chemical bonds-copy"
    assert copied.description == created.description
    assert copied.revision == 0 and not copied.approved
    result = planner.execute(ReviseStandaloneLessonRequest(copied.id, OWNER, 0, "Plan the copy"))
    assert result.content.plan.lesson_id == copied.id
    assert repo.require_by_id(LessonId(created.id)).content.plan is None


def test_other_user_cannot_copy_draft_or_missing_lesson(standalone):
    repo, _, _, _, created = standalone
    service = copy_service(repo)
    for identifier in (created.id, "lesson_00000000-0000-0000-0000-000000000099"):
        with pytest.raises(CourseNotFound):
            service.execute(CopyLessonRequest(identifier, OTHER))
    assert len(repo.items) == 1


@pytest.mark.parametrize("owner", [OWNER, OTHER])
def test_finished_copy_preserves_media_and_can_be_edited_independently(completed_standalone, owner):
    repo, source = completed_standalone
    interactive = LessonInteractive(
        lesson_plan_hash(source.content.plan), "No activity needed", None, None
    )
    source = replace(source, content=replace(source.content, interactive=interactive))
    repo.save(source)
    copied = copy_service(repo).execute(CopyLessonRequest(str(source.content.id), owner))
    saved = repo.require_by_id(LessonId(copied.id))
    assert str(saved.owner_id) == owner
    assert saved.revision == 0 and saved.approved
    for artifact in (
        saved.content.plan,
        saved.content.storyboard,
        saved.content.alignment,
        saved.content.animation,
    ):
        assert artifact.lesson_id == copied.id
    assert saved.content.animation.project_key == source.content.animation.project_key
    assert saved.content.style == source.content.style
    saved.content.interactive.validate_plan(saved.content.plan)
    uow = RecordingUnitOfWork(repo)
    updated = SaveStandaloneScript(repo, uow).execute(
        SaveStandaloneScriptRequest(
            copied.id,
            owner,
            0,
            tuple("New narration. " + s.narration_text for s in saved.content.storyboard.scenes),
        )
    )
    assert updated.content.animation is None
    assert repo.require_by_id(source.content.id) == source
    with pytest.raises(CourseNotFound):
        SaveStandaloneScript(repo, uow).execute(
            SaveStandaloneScriptRequest(copied.id, OTHER if owner == OWNER else OWNER, 1, ())
        )


def test_nonowner_copies_only_finished_snapshot_and_no_private_history(completed_standalone):
    repo, finished = completed_standalone
    draft = finished.edit_script(
        tuple("Private draft. " + s.narration_text for s in finished.content.storyboard.scenes)
    )
    repo.save(draft)
    service = copy_service(repo)
    public_copy = service.execute(CopyLessonRequest(str(draft.content.id), OTHER))
    private_copy = service.execute(CopyLessonRequest(str(draft.content.id), OWNER))
    public = repo.require_by_id(LessonId(public_copy.id))
    private = repo.require_by_id(LessonId(private_copy.id))
    assert public.content.storyboard.scenes == finished.content.storyboard.scenes
    assert public.content.animation is not None
    assert public.content.previous_versions == ()
    assert public.turns == ()
    assert public.description == finished.content.title
    assert private.content.storyboard.scenes == draft.content.storyboard.scenes
    assert private.content.previous_versions
    assert private.content.previous_versions[-1].id == private.content.id


@pytest.mark.parametrize("owner", [OWNER, OTHER])
def test_course_lesson_can_be_copied_to_owned_standalone(standalone, owner):
    repo, _, _, _, _ = standalone
    course = finished_course()
    courses = InMemoryCourses()
    courses.add(course)
    source = course.chapters[0].lessons[0]
    copied = copy_service(repo, courses).execute(
        CopyLessonRequest(str(source.id), owner, str(course.id))
    )
    assert copied.owner_id == owner
    assert copied.content.plan.lesson_id == copied.id
    assert copied.content.animation is not None
    assert courses.require_by_id(course.id) == course


def test_copy_title_stays_within_limit_when_copied_repeatedly(standalone):
    repo, _, _, _, created = standalone
    source = repo.require_by_id(LessonId(created.id))
    repo.save(replace(source, content=replace(source.content, title="A" * 120)))
    service = copy_service(repo)
    first = service.execute(CopyLessonRequest(created.id, OWNER))
    second = service.execute(CopyLessonRequest(first.id, OWNER))
    assert len(first.content.title) == 120
    assert len(second.content.title) == 120
    assert second.content.title.endswith("-copy")


def test_infeasible_course_outline_can_be_copied_as_an_unapproved_draft(standalone):
    from fixtures.lesson_plan import infeasible_lesson_plan
    from fixtures.syllabus import make_planned_course

    from app.courses.domain.lesson_plan import PlanGeneration

    repo, _, _, _, _ = standalone
    course, curriculum = make_planned_course()
    brief = curriculum.chapters[0].lessons[0]
    course = replace(course, owner_id=OWNER).approve().plan_lesson(
        brief.lesson_id, infeasible_lesson_plan(brief), PlanGeneration("test", 1, 0, 100)
    )
    courses = InMemoryCourses()
    courses.add(course)
    copied = copy_service(repo, courses).execute(
        CopyLessonRequest(brief.lesson_id, OWNER, str(course.id))
    )
    saved = repo.require_by_id(LessonId(copied.id))
    assert not saved.approved
    assert saved.content.plan.feasibility_status == "infeasible"
    assert saved.content.plan.recommended_video_minutes == brief.video_minutes + 2
    assert saved.content.plan.lesson_id == copied.id
    assert courses.require_by_id(course.id) == course


def test_copy_uses_the_chosen_title_trimmed(standalone):
    repo, _, _, _, created = standalone
    copied = copy_service(repo).execute(
        CopyLessonRequest(created.id, OWNER, title="  Bonds, my way  ")
    )
    assert copied.content.title == "Bonds, my way"
    assert repo.require_by_id(LessonId(created.id)).content.title == created.content.title


@pytest.mark.parametrize("owner", [OWNER, OTHER])
def test_chosen_title_names_the_copy_and_all_of_its_playable_versions(completed_standalone, owner):
    repo, finished = completed_standalone
    draft = finished.edit_script(
        tuple("Draft. " + s.narration_text for s in finished.content.storyboard.scenes)
    )
    repo.save(draft)
    copied = copy_service(repo).execute(
        CopyLessonRequest(str(draft.content.id), owner, title="My version")
    )
    saved = repo.require_by_id(LessonId(copied.id))
    assert saved.content.title == "My version"
    assert {v.title for v in saved.content.previous_versions} <= {"My version"}


@pytest.mark.parametrize("title", ["", "   ", "A" * 121])
def test_copy_rejects_blank_or_overlong_titles_without_adding_a_lesson(standalone, title):
    repo, _, _, _, created = standalone
    with pytest.raises(CourseError):
        copy_service(repo).execute(CopyLessonRequest(created.id, OWNER, title=title))
    assert len(repo.items) == 1
