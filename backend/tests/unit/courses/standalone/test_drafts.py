import pytest

from app.courses.application.standalone import GetStandaloneLesson, UpdateStandaloneLesson
from app.courses.application.standalone_dto import (
    ReviseStandaloneLessonRequest,
    StandaloneLessonRequest,
    UpdateStandaloneLessonRequest,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import LessonId


def test_resaving_a_draft_preserves_identity_and_planning_uses_the_saved_details(standalone):
    repo, uow, agent, planner, created = standalone
    updated = UpdateStandaloneLesson(repo, uow).execute(
        UpdateStandaloneLessonRequest(
            created.id, created.owner_id, 0, " Water molecules ", " Explain water ", 5
        )
    )
    assert updated.id == created.id
    saved = repo.require_by_id(LessonId(created.id))
    assert (saved.content.title, saved.description, saved.content.minutes) == (
        "Water molecules",
        "Explain water",
        5,
    )
    assert updated.revision == 1
    assert updated.content.plan is None
    restored = GetStandaloneLesson(repo, uow).execute(
        StandaloneLessonRequest(created.id, created.owner_id)
    )
    assert restored == updated
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, created.owner_id, 1))
    assert planned.content.plan is not None
    assert planned.content.title == "Water molecules"


def test_draft_updates_reject_stale_requests_and_other_owners(standalone):
    repo, uow, _, _, created = standalone
    service = UpdateStandaloneLesson(repo, uow)
    with pytest.raises(CourseConflict):
        service.execute(
            UpdateStandaloneLessonRequest(
                created.id, created.owner_id, 9, "Changed", "New brief", 5
            )
        )
    with pytest.raises(CourseNotFound):
        service.execute(
            UpdateStandaloneLessonRequest(
                created.id,
                "user_00000000-0000-0000-0000-000000000002",
                0,
                "Changed",
                "New brief",
                5,
            )
        )
    assert repo.require_by_id(LessonId(created.id)).revision == 0


def test_invalid_draft_update_keeps_previous_details(standalone):
    repo, uow, _, _, created = standalone
    with pytest.raises(CourseError):
        UpdateStandaloneLesson(repo, uow).execute(
            UpdateStandaloneLessonRequest(
                created.id, created.owner_id, 0, "Changed", "New brief", 11
            )
        )
    assert repo.require_by_id(LessonId(created.id)).content.minutes == 3


def test_updated_details_start_a_new_outline_and_noop_does_not_bump_revision(standalone):
    repo, uow, _, planner, created = standalone
    service = UpdateStandaloneLesson(repo, uow)
    unchanged = service.execute(
        UpdateStandaloneLessonRequest(
            created.id, created.owner_id, 0, created.content.title, created.description, 3
        )
    )
    assert unchanged == created
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, created.owner_id, 0))
    updated = service.execute(
        UpdateStandaloneLessonRequest(
            created.id, created.owner_id, planned.revision, "Changed", "New brief", 5
        )
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.plan is None
    assert saved.description == "New brief"
    assert saved.content.title == "Changed"
    assert not saved.approved
    assert updated.revision == planned.revision + 1
