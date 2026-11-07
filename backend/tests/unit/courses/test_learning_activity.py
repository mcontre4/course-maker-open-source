from datetime import UTC, datetime

import pytest
from fakes.courses import RecordingUnitOfWork
from fakes.learning_activity import InMemoryLearningActivities, SteppingClock

from app.courses.application.learning_activity import (
    GetLearningActivity,
    GetLearningActivityRequest,
    RecordLearningActivity,
    RecordLearningActivityRequest,
)
from app.shared.domain.errors import InvalidIdentifierError

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"
LESSON = "lesson_00000000-0000-0000-0000-000000000001"
COURSE = "course_00000000-0000-0000-0000-000000000001"
START = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def activities():
    return InMemoryLearningActivities()


@pytest.fixture
def record(activities):
    return RecordLearningActivity(activities, SteppingClock(START), RecordingUnitOfWork(activities))


def recent(activities, owner=OWNER, limit=50):
    return GetLearningActivity(activities).execute(GetLearningActivityRequest(owner, limit)).items


def test_most_recently_opened_item_comes_first(activities, record):
    record.execute(RecordLearningActivityRequest(OWNER, COURSE))
    record.execute(RecordLearningActivityRequest(OWNER, LESSON))

    assert [item.item_id for item in recent(activities)] == [LESSON, COURSE]


def test_reopening_an_item_moves_it_forward_without_duplicating_it(activities, record):
    record.execute(RecordLearningActivityRequest(OWNER, COURSE))
    record.execute(RecordLearningActivityRequest(OWNER, LESSON))
    record.execute(RecordLearningActivityRequest(OWNER, COURSE))

    assert [item.item_id for item in recent(activities)] == [COURSE, LESSON]


def test_open_time_is_reported_as_an_iso_timestamp(activities, record):
    record.execute(RecordLearningActivityRequest(OWNER, COURSE))

    assert recent(activities)[0].last_opened_at == "2026-11-01T09:00:00+00:00"


def test_activity_stays_private_to_its_owner(activities, record):
    record.execute(RecordLearningActivityRequest(OWNER, COURSE))

    assert recent(activities, OTHER) == ()


def test_recent_activity_honours_the_limit(activities, record):
    record.execute(RecordLearningActivityRequest(OWNER, COURSE))
    record.execute(RecordLearningActivityRequest(OWNER, LESSON))

    assert [item.item_id for item in recent(activities, limit=1)] == [LESSON]


def test_recording_commits_one_transaction(activities):
    uow = RecordingUnitOfWork(activities)

    RecordLearningActivity(activities, SteppingClock(START), uow).execute(
        RecordLearningActivityRequest(OWNER, COURSE)
    )

    assert uow.commits == 1


@pytest.mark.parametrize(
    "item_id",
    [
        "chapter_00000000-0000-0000-0000-000000000001",
        "user_00000000-0000-0000-0000-000000000001",
        "course_not-a-uuid",
        "",
    ],
)
def test_only_courses_and_lessons_can_be_recorded(activities, record, item_id):
    with pytest.raises(InvalidIdentifierError):
        record.execute(RecordLearningActivityRequest(OWNER, item_id))

    assert recent(activities) == ()
