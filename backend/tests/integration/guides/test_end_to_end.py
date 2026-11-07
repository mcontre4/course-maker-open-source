import pytest
from fixtures.guide_answer import RICH_GUIDE_ANSWER
from pydantic_ai import ConversationTypeAdapter
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.guide import SqlAlchemyGuideRepository
from app.courses.domain.guide import GuideThreadId

pytestmark = pytest.mark.integration


def create_lesson(client, title="Chemical bonds"):
    response = client.post(
        "/api/v1/lessons",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": title,
            "description": "Explain bonds",
            "minutes": 3,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_chat(client, resource_id, guide="lesson"):
    response = client.post(
        "/api/v1/guides/chats",
        json={"resourceId": resource_id, "guide": guide, "title": "Explore ideas"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def send(client, chat, message, request_id=None):
    response = client.post(
        f"/api/v1/guides/chats/{chat['id']}/messages",
        json={
            "message": message,
            "requestId": request_id or f"request-{chat['revision']}",
            "expectedRevision": chat["revision"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_rich_answers_round_trip_through_agent_http_and_postgres(
    guide_client, guide_client_factory, model_script
):
    lesson = create_lesson(guide_client)
    for role in ("lesson", "storyboard", "animation"):
        chat = create_chat(guide_client, lesson["id"], role)
        saved = send(guide_client, chat, "Explain bonds visually")
        assert saved["turns"][-1]["assistant"] == RICH_GUIDE_ANSWER
        assert "Answer(title: string" in model_script.calls[-1][1].instructions
        with guide_client_factory() as reopened:
            restored = reopened.get(f"/api/v1/guides/chats/{chat['id']}").json()
            assert restored["turns"] == saved["turns"]
        assert guide_client.get(f"/api/v1/lessons/{lesson['id']}").json()["revision"] == 0


def test_chats_tools_memories_versions_and_restart(
    guide_client, guide_client_factory, guide_database, model_script
):
    client = guide_client
    lesson = create_lesson(client)
    chat = create_chat(client, lesson["id"])
    chat = send(client, chat, "Remember Spanish")
    chat = send(client, chat, "Remember audience")
    chat = send(client, chat, "Revise initial outline")
    first = client.get(f"/api/v1/lessons/{lesson['id']}").json()
    assert first["revision"] == 1
    assert not first["approved"]
    chat = send(client, chat, "Why these examples?")
    assert client.get(f"/api/v1/lessons/{lesson['id']}").json() == first
    chat = send(client, chat, "Revise with changed introduction")
    assert len(client.specialist.calls) == 2
    retried = client.post(
        f"/api/v1/guides/chats/{chat['id']}/messages",
        json={
            "message": "Revise with changed introduction",
            "requestId": "request-4",
            "expectedRevision": 4,
        },
    )
    assert retried.status_code == 200
    assert retried.json()["revision"] == 5
    assert len(client.specialist.calls) == 2
    chat = send(client, chat, "Compare 1 2")
    assert "Changed introduction" in chat["turns"][-1]["assistant"]
    chat = send(client, chat, "Read version 1")
    chat = send(client, chat, "List versions")
    chat = send(client, chat, "Restore 1")
    restored = client.get(f"/api/v1/lessons/{lesson['id']}").json()
    assert restored["revision"] == 3
    assert restored["content"]["plan"] == first["content"]["plan"]
    versions = client.get(
        "/api/v1/guides/outline-versions", params={"resource_id": lesson["id"]}
    ).json()["items"]
    assert [v["revision"] for v in versions] == [3, 2, 1]
    assert [v["parent_revision"] for v in versions] == [2, 1, None]
    assert versions[0]["source_message_id"] == chat["turns"][-1]["id"]
    chat = send(client, chat, "Read current outline")
    assert "Assignment" in chat["turns"][-1]["assistant"]

    # A new app, agent, HTTP client, and SQL session resume durable state.
    with guide_client_factory() as reopened:
        saved = reopened.get(f"/api/v1/guides/chats/{chat['id']}").json()
        assert saved["turns"] == chat["turns"]
        second_chat = create_chat(reopened, lesson["id"], "storyboard")
        assert not second_chat["turns"]
        second_chat = send(reopened, second_chat, "Hello")
        assert "Chemistry beginners" in str(model_script.calls[-1][1].instructions)
        assert "Spanish" in str(model_script.calls[-1][1].instructions)
        chat = send(reopened, saved, "Find audience")
        assert "Remember audience" in chat["turns"][-1]["assistant"]
        other = create_lesson(reopened, "Physics")
        memories = reopened.get(
            "/api/v1/guides/memories", params={"resource_id": other["id"]}
        ).json()["items"]
        assert [m["key"] for m in memories] == ["language"]
        initial = reopened.post(
            f"/api/v1/lessons/{other['id']}/plan",
            json={"expectedRevision": 0, "message": "Generate the first outline"},
        )
        assert initial.status_code == 200, initial.text
        assert any("Spanish" in value for value in reopened.specialist.calls[-1].guide.assumptions)
        chat = send(reopened, chat, "Forget language")
        memories = reopened.get(
            "/api/v1/guides/memories", params={"resource_id": other["id"]}
        ).json()["items"]
        assert memories == []
    with Session(guide_database) as session:
        stored = SqlAlchemyGuideRepository(session).require_by_id(GuideThreadId(chat["id"]))
        conversation = ConversationTypeAdapter.validate_json(stored.history_json)
        assert len(conversation.messages) > len(chat["turns"])
        assert conversation.conversation_id


def test_manual_edits_are_snapshotted_and_another_owner_cannot_read(
    guide_client, guide_client_factory
):
    client = guide_client
    lesson = create_lesson(client)
    chat = send(client, create_chat(client, lesson["id"]), "Revise initial outline")
    lesson = client.get(f"/api/v1/lessons/{lesson['id']}").json()
    outline = lesson["content"]["plan"]
    outline["beats"][0]["title"] = "Manual introduction"
    outline.pop("lessonId")
    outline.pop("sources")
    edited = client.put(
        f"/api/v1/lessons/{lesson['id']}/outline",
        json={"expectedRevision": lesson["revision"], "outline": outline},
    )
    assert edited.status_code == 200, edited.text
    versions = client.get(
        "/api/v1/guides/outline-versions", params={"resource_id": lesson["id"]}
    ).json()["items"]
    assert "Manual introduction" in versions[0]["outline_json"]
    with guide_client_factory("user_00000000-0000-0000-0000-000000000002") as other:
        assert other.get(f"/api/v1/guides/chats/{chat['id']}").status_code == 404
        for path in ("chats", "memories", "outline-versions"):
            assert (
                other.get(
                    "/api/v1/guides/" + path, params={"resource_id": lesson["id"]}
                ).status_code
                == 404
            )


def test_memory_correction_and_revision_conflicts(guide_client):
    client = guide_client
    lesson = create_lesson(client)
    chat = send(client, create_chat(client, lesson["id"]), "Remember audience")
    memories = client.get("/api/v1/guides/memories", params={"resource_id": lesson["id"]}).json()[
        "items"
    ]
    memory = memories[0]
    body = {"resourceId": lesson["id"], "content": "Advanced chemistry", "expectedRevision": 1}
    path = f"/api/v1/guides/memories/{memory['id']}"
    assert client.put(path, json=body).status_code == 200
    assert client.put(path, json=body).status_code == 409
    stale = client.post(
        f"/api/v1/guides/chats/{chat['id']}/messages",
        json={"message": "Hello", "requestId": "stale", "expectedRevision": 0},
    )
    assert stale.status_code == 409
    assert (
        client.delete(
            path, params={"resource_id": lesson["id"], "expected_revision": 2}
        ).status_code
        == 200
    )


def test_course_guide_uses_independent_threads_and_specialist(guide_client, guide_client_factory):
    client = guide_client
    response = client.post(
        "/api/v1/courses",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": "Python",
            "description": "Learn Python",
            "duration": {"mode": "total", "hours": 2},
        },
    )
    assert response.status_code == 201, response.text
    course = response.json()
    chat = create_chat(client, course["id"], "syllabus")
    chat = send(client, chat, "Revise initial syllabus")
    planned = client.get(f"/api/v1/courses/{course['id']}").json()
    assert planned["chapters"]
    chat = send(client, chat, "Revise with changed title")
    versions = client.get(
        "/api/v1/guides/outline-versions", params={"resource_id": course["id"]}
    ).json()["items"]
    assert [v["revision"] for v in versions] == [2, 1]
    chat = send(client, chat, "Restore 1")
    assert client.get(f"/api/v1/courses/{course['id']}").json()["title"] == planned["title"]
    with guide_client_factory() as reopened:
        assert reopened.get(f"/api/v1/guides/chats/{chat['id']}").json()["revision"] == 3
        other_chat = create_chat(reopened, course["id"], "syllabus")
        assert not other_chat["turns"]


def test_new_chat_gets_a_durable_title_from_its_first_message(guide_client, guide_client_factory):
    lesson = create_lesson(guide_client)
    response = guide_client.post(
        "/api/v1/guides/chats",
        json={"resourceId": lesson["id"], "title": "New chat"},
    )
    assert response.status_code == 201, response.text
    chat = send(guide_client, response.json(), "Explain linked lists")
    assert chat["title"] == "Explain linked lists"
    chat = send(guide_client, chat, "Now explain nodes")
    assert chat["title"] == "Explain linked lists"
    with guide_client_factory() as reopened:
        listed = reopened.get("/api/v1/guides/chats", params={"resource_id": lesson["id"]}).json()[
            "items"
        ]
        assert listed[0]["title"] == "Explain linked lists"
