import pytest

from app.courses.domain.identifiers import LessonId

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("video_http", ["standalone"], indirect=True)
@pytest.mark.parametrize("restart", ["script", "speech", "animation"])
def test_video_forwards_explicit_restart(video_http, restart):
    client, path, body, service = video_http
    response = client.post(path, json={**body, "regenerateFrom": restart})
    assert response.status_code == 200, response.text
    assert service.requests[0].regenerate_from == restart


@pytest.mark.parametrize("video_http", ["standalone"], indirect=True)
@pytest.mark.parametrize("restart", ["unknown", "", True])
def test_video_rejects_invalid_restart_before_generation(video_http, restart):
    client, path, body, service = video_http
    assert client.post(path, json={**body, "regenerateFrom": restart}).status_code == 422
    assert not service.requests


@pytest.mark.parametrize("field,value", [("title", "Bonds"), ("description", "Explain bonds")])
def test_create_and_update_allow_either_detail_to_be_omitted(standalone_details_http, field, value):
    client, repository = standalone_details_http
    response = client.post(
        "/api/v1/lessons",
        json={
            field: value,
            "minutes": 3,
            "style": {"visualStyleId": "flat-vector-science"},
        },
    )
    assert response.status_code == 201, response.text
    lesson = response.json()
    assert lesson["content"]["title"] == lesson["description"] == value
    response = client.put(
        f"/api/v1/lessons/{lesson['id']}",
        json={
            field: "New topic",
            "minutes": 3,
            "expectedRevision": lesson["revision"],
            "style": {"visualStyleId": "flat-vector-science"},
        },
    )
    assert response.status_code == 200, response.text
    saved = repository.require_by_id(LessonId(lesson["id"]))
    assert saved.content.title == saved.description == "New topic"


def test_empty_lesson_is_rejected_with_actionable_error(standalone_details_http):
    client, repository = standalone_details_http
    response = client.post(
        "/api/v1/lessons",
        json={
            "minutes": 3,
            "style": {"visualStyleId": "flat-vector-science"},
        },
    )
    assert response.status_code == 422, response.text
    assert "title or describe" in response.json()["detail"]
