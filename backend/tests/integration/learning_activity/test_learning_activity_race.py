from datetime import UTC, datetime

import pytest
from sqlalchemy import event

from app.courses.adapters.persistence.learning_activity import (
    LearningActivityRecord,
    SqlAlchemyLearningActivities,
)
from app.courses.domain.identifiers import CourseId
from app.courses.domain.learning_activity import LearningActivity
from app.courses.domain.standalone import LessonOwnerId

pytestmark = pytest.mark.integration

OWNER = "user_00000000-0000-0000-0000-000000000001"
COURSE = "course_00000000-0000-0000-0000-000000000001"
THEIRS = datetime(2026, 11, 1, 9, 0, 0, tzinfo=UTC)
OURS = datetime(2026, 11, 1, 9, 0, 1, tzinfo=UTC)


def test_two_simultaneous_first_opens_both_succeed(activity_sessions):
    with activity_sessions() as session:

        def other_request_commits_first(*_):
            with activity_sessions() as other:
                other.add(
                    LearningActivityRecord(owner_id=OWNER, item_id=COURSE, last_opened_at=THEIRS)
                )
                other.commit()

        event.listen(session, "before_flush", other_request_commits_first, once=True)
        SqlAlchemyLearningActivities(session).save(
            LearningActivity(LessonOwnerId(OWNER), CourseId(COURSE), OURS.isoformat())
        )
        session.commit()

    with activity_sessions() as session:
        recent = SqlAlchemyLearningActivities(session).recent_by_owner(LessonOwnerId(OWNER), 10)
        assert [str(item.item_id) for item in recent] == [COURSE]
