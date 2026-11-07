from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from fixtures.creator_app import LocalMediaStorage, create_creator_test_app

pytestmark = pytest.mark.integration

COURSE = "course_00000000-0000-0000-0000-000000000001"
LESSON = "lesson_00000000-0000-0000-0000-000000000001"


def opened_ids(client):
    response = client.get("/api/v1/learning-activity")
    assert response.status_code == 200, response.text
    return [item["itemId"] for item in response.json()["items"]]


def test_reopening_moves_an_item_to_the_front_across_requests(activity_sessions):
    app = create_creator_test_app(activity_sessions, LocalMediaStorage())
    with TestClient(app) as learner:
        assert learner.put(f"/api/v1/learning-activity/{COURSE}").status_code == 204
        assert learner.put(f"/api/v1/learning-activity/{LESSON}").status_code == 204
        assert opened_ids(learner) == [LESSON, COURSE]
        assert learner.put(f"/api/v1/learning-activity/{COURSE}").status_code == 204
        assert opened_ids(learner) == [COURSE, LESSON]
        limited = learner.get("/api/v1/learning-activity?limit=1").json()["items"]
        assert [item["itemId"] for item in limited] == [COURSE]
        assert datetime.fromisoformat(limited[0]["lastOpenedAt"]).tzinfo is not None
        assert learner.get("/api/v1/learning-activity?limit=0").status_code == 422


def test_activity_is_private_to_the_person_who_opened_it(activity_sessions):
    app = create_creator_test_app(activity_sessions, LocalMediaStorage())
    with TestClient(app) as learner, TestClient(app) as other:
        learner.put(f"/api/v1/learning-activity/{COURSE}")
        assert opened_ids(learner) == [COURSE]
        assert opened_ids(other) == []


def test_only_course_and_lesson_ids_are_accepted(activity_sessions):
    app = create_creator_test_app(activity_sessions, LocalMediaStorage())
    with TestClient(app) as learner:
        rejected = learner.put(
            "/api/v1/learning-activity/chapter_00000000-0000-0000-0000-000000000001"
        )
        assert rejected.status_code == 422, rejected.text
        assert opened_ids(learner) == []
