import pytest
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.domain.identifiers import CourseId

pytestmark = pytest.mark.integration


def test_complete_manual_learning_flow(api, draft_payload, syllabus_payload, clean_mysql):
    created = api.post("/api/v1/courses", json=draft_payload)
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]
    path = f"/api/v1/courses/{course_id}"
    assert api.get(path).json()["status"] == "draft"
    assert api.get("/api/v1/courses", params={"search": "Python"}).json()["total"] == 1
    assert api.post(path + "/syllabus/approve").status_code == 409
    syllabus = api.put(path + "/syllabus", json=syllabus_payload)
    assert syllabus.status_code == 200, syllabus.text
    lesson = syllabus.json()["chapters"][0]["lessons"][0]
    assert "answer" not in lesson["quiz"][0] and "explanation" not in lesson["quiz"][0]
    lesson_path = path + "/lessons/" + lesson["id"]
    assert api.get(lesson_path).status_code == 200
    assert (
        api.patch(lesson_path + "/topics", json={"topic": "Values", "operation": "add"}).status_code
        == 200
    )
    assert api.post(path + "/syllabus/approve").json()["status"] == "ready"
    assert api.put(path, json=draft_payload).status_code == 409
    assert api.post(lesson_path + "/quiz/attempts", json={"answers": [0]}).status_code == 409
    assert api.post(lesson_path + "/review").status_code == 200
    assert api.post(lesson_path + "/review").json()["reviewed"] == [lesson["id"]]
    assert api.post(lesson_path + "/quiz/attempts", json={"answers": [100]}).status_code == 422
    failed = api.post(lesson_path + "/quiz/attempts", json={"answers": [1]})
    assert failed.status_code == 201 and not failed.json()["passed"]
    passed = api.post(lesson_path + "/quiz/attempts", json={"answers": [0]})
    assert passed.status_code == 201 and passed.json()["passed"]
    assert passed.json()["feedback"] == [{"correct": True, "explanation": "x is a name"}]
    assert api.get(path + "/progress").json()["percent"] == 100
    with Session(clean_mysql) as session:
        course = MySqlCourseRepository(session).require_by_id(CourseId(course_id))
        assert len(course.attempts) == 2 and course.completed == (lesson["id"],)
    assert api.delete(path).status_code == 204
    assert api.get(path).status_code == 404


def test_validation_auth_cors_and_deferred_ai(api, draft_payload):
    unauthorized = api.get("/api/v1/courses", headers={"Cookie": ""})
    assert unauthorized.status_code == 401
    assert api.get("/health/live").json() == {"status": "ok"}
    assert api.get("/health/ready").json() == {
        "database": True,
        "cache": True,
        "storageConfigured": False,
    }
    assert api.get("/api/v1/courses/not-an-id").status_code == 422
    assert api.get("/api/v1/courses", params={"limit": 101}).status_code == 422
    assert api.post("/api/v1/courses", json={**draft_payload, "title": " "}).status_code == 422
    course = api.post("/api/v1/courses", json=draft_payload).json()
    path = "/api/v1/courses/" + course["id"]
    assert api.post(path + "/chat").status_code == 501
    assert api.post(path + "/lessons/generate").status_code == 409
    assert (
        api.post(
            path + "/assets/uploads", json={"contentType": "image/png", "size": 10}
        ).status_code
        == 503
    )
    preflight = api.options(
        "/api/v1/courses",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    restored = api.get(path, headers={"Origin": "http://localhost:5173"})
    assert restored.status_code == 200
    exposed = restored.headers["access-control-expose-headers"].lower().split(", ")
    assert "x-active-operation" in exposed
    assert "x-operation-error" in exposed
    blocked = api.options(
        "/api/v1/courses",
        headers={"Origin": "https://unknown.example", "Access-Control-Request-Method": "POST"},
    )
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


def test_user_registration_on_mysql(api):
    body = {"email": "learner@example.com", "first_name": "Ada", "last_name": "Lovelace"}
    created = api.post("/users", json=body)
    assert created.status_code == 201, created.text
    assert created.json()["id"].startswith("user_")
    assert api.post("/users", json=body).status_code == 409


def test_catalog_is_cached_in_redis(api, redis_server):
    client = redis_server.get_client()
    client.delete("course-maker:catalog:v1")
    result = api.get("/api/v1/catalog/topics")
    assert result.status_code == 200 and result.json()["topics"]
    assert client.ttl("course-maker:catalog:v1") > 0
    client.set("course-maker:catalog:v1", "bad-json")
    assert api.get("/api/v1/catalog/topics").status_code == 200


def test_manual_content_can_be_added_after_approval(api, draft_payload, syllabus_payload):
    lesson = syllabus_payload["chapters"][0]["lessons"][0]
    lesson["videoUrl"], lesson["quiz"] = None, []
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    path = "/api/v1/courses/" + course_id
    outlined = api.put(path + "/syllabus", json=syllabus_payload).json()
    lesson_id = outlined["chapters"][0]["lessons"][0]["id"]
    lesson_path = path + "/lessons/" + lesson_id
    assert api.post(path + "/syllabus/approve").status_code == 200
    assert api.post(lesson_path + "/review").status_code == 409
    asset_id = "asset_00000000-0000-0000-0000-000000000123"
    updated = api.put(
        lesson_path + "/content",
        json={
            "videoAssetId": asset_id,
            "quiz": [
                {
                    "prompt": "Which is a variable?",
                    "options": ["x", "1"],
                    "answer": 0,
                    "explanation": "x is a name",
                }
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert api.get(lesson_path).json()["videoAssetId"] == asset_id
    assert api.post(lesson_path + "/review").status_code == 200
    assert api.post(lesson_path + "/quiz/attempts", json={"answers": [0]}).status_code == 201
    assert len(api.get(lesson_path + "/quiz/attempts").json()["items"]) == 1
    assert api.put(lesson_path + "/content", json={}).status_code == 409


def test_non_ascii_bearer_credentials_are_rejected_as_unauthorized(api):
    response = api.get("/health/ready", headers={"Authorization": b"Bearer invalid-\xff"})
    assert response.status_code == 401


def test_user_transport_rejects_whitespace_names_and_extra_fields(api):
    body = {"email": "learner@example.com", "first_name": " ", "last_name": "Lovelace"}
    assert api.post("/users", json=body).status_code == 422
    body["first_name"] = "Ada"
    assert api.post("/users", json={**body, "is_admin": True}).status_code == 422


def test_topic_edit_does_not_corrupt_other_lessons(api, draft_payload, syllabus_payload):
    from copy import deepcopy

    chapter = syllabus_payload["chapters"][0]
    second_lesson = deepcopy(chapter["lessons"][0])
    second_lesson.update(title="Functions", topics=["Calls"])
    chapter["lessons"].append(second_lesson)
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    path = "/api/v1/courses/" + course_id
    syllabus = api.put(path + "/syllabus", json=syllabus_payload).json()
    first, second = syllabus["chapters"][0]["lessons"]
    edited = api.patch(
        path + "/lessons/" + first["id"] + "/topics", json={"topic": "Values", "operation": "add"}
    )
    assert edited.status_code == 200, edited.text
    assert api.get(path).json()["chapters"][0]["lessons"][1] == second
