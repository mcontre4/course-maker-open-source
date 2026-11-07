"""Production wiring must serve saved chats after the real migration chain."""

import pytest

pytestmark = pytest.mark.integration


def test_migrated_application_serves_guide_chats_and_context(api):
    lesson_response = api.post(
        "/api/v1/lessons",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": "Linked lists",
            "description": "Explain nodes and links",
            "minutes": 3,
        },
    )
    assert lesson_response.status_code == 201, lesson_response.text
    resource_id = lesson_response.json()["id"]
    query = {"resource_id": resource_id}
    for endpoint in ("chats", "memories", "outline-versions"):
        response = api.get(f"/api/v1/guides/{endpoint}", params=query)
        assert response.status_code == 200, response.text
        assert response.json() == {"items": []}

    created = api.post(
        "/api/v1/guides/chats",
        json={"resourceId": resource_id, "guide": "lesson", "title": "First ideas"},
    )
    assert created.status_code == 201, created.text
    chat = created.json()
    second = api.post(
        "/api/v1/guides/chats",
        json={"resourceId": resource_id, "guide": "lesson", "title": "Another approach"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] != chat["id"]
    saved = api.get(f"/api/v1/guides/chats/{chat['id']}")
    assert saved.status_code == 200, saved.text
    assert saved.json() == chat
    listed = api.get("/api/v1/guides/chats", params=query)
    assert {item["title"] for item in listed.json()["items"]} == {"First ideas", "Another approach"}
    # Missing provider configuration is a readable application error, with JSON transport.
    unavailable = api.post(
        f"/api/v1/guides/chats/{chat['id']}/messages",
        json={"message": "Explain nodes", "requestId": "first", "expectedRevision": 0},
    )
    assert unavailable.status_code == 503, unavailable.text
    assert isinstance(unavailable.json()["detail"], str)
    assert api.get(f"/api/v1/guides/chats/{chat['id']}").json()["revision"] == 0
