from dataclasses import asdict, replace

import pytest
from fixtures.lesson_plan import infeasible_lesson_plan, lesson_plan
from fixtures.outline import outline_input
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.application.dto import lesson_response
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_plan import PlanGeneration

pytestmark = pytest.mark.integration


def test_infeasible_outline_round_trips_through_storage_http_and_manual_editing(api, clean_mysql):
    draft = api.post(
        "/api/v1/lessons",
        json={
            "title": "Water",
            "description": "Explain water",
            "minutes": 3,
            "style": {"visualStyleId": "flat-vector-science"},
        },
    ).json()
    path = "/api/v1/lessons/" + draft["id"]
    with Session(clean_mysql) as session:
        repo = SqlAlchemyStandaloneLessons(session)
        lesson = repo.require_by_id(LessonId(draft["id"]))
        plan = infeasible_lesson_plan(lesson.brief())
        plan = replace(
            plan,
            recommended_video_minutes=12,
            beats=(
                replace(plan.beats[0], seconds=360),
                replace(plan.beats[0], seconds=360, check_question="", expected_answer=""),
            ),
            examples=(replace(plan.examples[0], steps=()),),
        )
        planned = lesson.revise("Plan", plan, PlanGeneration("test", 1, 0, 100))
        repo.save(planned)
        session.commit()
    response = api.get(path)
    assert response.status_code == 200, response.text
    exposed = response.json()["content"]["plan"]
    assert exposed["feasibilityStatus"] == "infeasible"
    assert exposed["recommendedVideoMinutes"] == 12
    assert exposed["feasibilityExplanation"] == plan.feasibility_explanation
    assert response.json()["content"]["minutes"] == 3
    rejected = api.post(path + "/approve", json={"expectedRevision": planned.revision})
    assert rejected.status_code == 409, rejected.text
    assert "scope needs review" in rejected.text
    body = asdict(outline_input(lesson_response(planned.content).plan))
    body["beats"][0]["teaching_notes"] = "Keep the context before the conclusion."
    result = api.put(
        path + "/outline", json={"expectedRevision": planned.revision, "outline": body}
    )
    assert result.status_code == 200, result.text
    assert result.json()["content"]["plan"]["recommendedScopeAdjustment"] == (
        plan.recommended_scope_adjustment
    )
    with Session(clean_mysql) as session:
        saved = SqlAlchemyStandaloneLessons(session).require_by_id(LessonId(draft["id"]))
        assert saved.content.plan.feasibility_status == "infeasible"
        assert saved.content.plan.beats[1].check_question == ""
        assert saved.content.plan.examples[0].steps == ()
        assert saved.content.minutes == 3
        assert not saved.approved
    body["recommended_video_minutes"] = None
    rejected = api.put(
        path + "/outline",
        json={"expectedRevision": result.json()["revision"], "outline": body},
    )
    assert rejected.status_code == 422, rejected.text
    assert api.get(path).json() == result.json()


def test_build_outline_through_production_http_wiring_persists_and_reloads(
    planned_lesson_api, clean_mysql
):
    api, agent = planned_lesson_api
    payload = {
        "style": {"visualStyleId": "flat-vector-science"},
        "title": "Chemical bonds",
        "description": "Explain how atoms share electrons in water",
        "minutes": 3,
        "generationMode": "fast",
    }
    created = api.post("/api/v1/lessons", json=payload)
    assert created.status_code == 201, created.text
    draft = created.json()
    path = "/api/v1/lessons/" + draft["id"]
    result = api.post(
        path + "/plan",
        json={
            "message": payload["description"],
            "expectedRevision": draft["revision"],
            "generationMode": "fast",
        },
    )
    assert result.status_code == 200, result.text
    planned = result.json()
    assert planned["revision"] == draft["revision"] + 1
    assert planned["content"]["plan"]["beats"]
    assert planned["turns"][0]["user"] == payload["description"]
    assert len(agent.calls) == 1
    assert str(agent.calls[0].brief.lesson_id) == draft["id"]
    assert agent.calls[0].message == payload["description"]
    with Session(clean_mysql) as session:
        saved = SqlAlchemyStandaloneLessons(session).require_by_id(LessonId(draft["id"]))
        assert saved.content.plan == lesson_plan(agent.calls[0].brief)
        assert saved.revision == planned["revision"]
    assert api.get(path).json() == planned
    assert api.get("/api/v1/lessons").json()["items"] == [planned]
    assert api.get(path + "/spend").status_code == 403
    approved = api.post(path + "/approve", json={"expectedRevision": planned["revision"]})
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved"]
    assert approved.json()["content"]["plan"] == planned["content"]["plan"]
    assert len(agent.calls) == 1


def test_outline_edit_persists_exactly_approves_without_ai_and_rejects_invalid_saves(
    api, clean_mysql
):
    created = api.post(
        "/api/v1/lessons",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": "Water",
            "description": "Explain water",
            "minutes": 3,
        },
    ).json()
    path = "/api/v1/lessons/" + created["id"]
    with Session(clean_mysql) as session:
        repo = SqlAlchemyStandaloneLessons(session)
        lesson = repo.require_by_id(LessonId(created["id"]))
        planned = lesson.revise(
            "Plan", lesson_plan(lesson.brief()), PlanGeneration("test", 1, 0, 100)
        )
        repo.save(planned)
        session.commit()
    body = {
        "expectedRevision": 1,
        "outline": asdict(outline_input(lesson_response(planned.content).plan)),
    }
    body["outline"]["beats"][0]["teaching_notes"] = (
        "  Show hydrogen and oxygen sharing electrons.\n    Keep this indented example.\n"
    )
    body["outline"]["objectives"] = ["Explain how atoms share electrons"]
    result = api.put(path + "/outline", json=body)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved["revision"] == 2
    assert not saved["approved"]
    assert saved["turns"] == api.get(path).json()["turns"]
    assert (
        saved["content"]["plan"]["beats"][0]["teachingNotes"]
        == body["outline"]["beats"][0]["teaching_notes"]
    )
    assert api.get(path).json() == saved
    assert api.put(path + "/outline", json=body).status_code == 409
    approved = api.post(path + "/approve", json={"expectedRevision": 2, "generationMode": "fast"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved"]
    assert approved.json()["content"]["plan"] == saved["content"]["plan"]
    body["expectedRevision"] = 3
    unchanged = api.put(path + "/outline", json=body)
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json() == approved.json()
    body["outline"]["beats"][0]["seconds"] = 500
    assert api.put(path + "/outline", json=body).status_code == 422
    assert api.get(path).json() == approved.json()
    body["outline"]["beats"][0]["seconds"] = True
    assert api.put(path + "/outline", json=body).status_code == 422
    body["outline"]["beats"][0]["seconds"] = 180
    body["outline"]["beats"][0]["teaching_notes"] = "Updated again"
    changed = api.put(path + "/outline", json=body)
    assert changed.status_code == 200, changed.text
    assert not changed.json()["approved"]
    api.cookies.clear()
    body["expectedRevision"] = changed.json()["revision"]
    from fixtures.authenticated_client import authenticate_client

    authenticate_client(api, "user_00000000-0000-0000-0000-000000000002")
    assert api.put(path + "/outline", json=body).status_code == 404


def test_draft_details_update_round_trip_and_revision_conflict(api):
    payload = {
        "style": {"visualStyleId": "flat-vector-science"},
        "title": "Bonds",
        "description": "Explain bonds",
        "minutes": 3,
    }
    lesson = api.post("/api/v1/lessons", json=payload).json()
    path = "/api/v1/lessons/" + lesson["id"]
    update = {**payload, "title": "Water", "minutes": 5, "expectedRevision": 0}
    result = api.put(path, json=update)
    assert result.status_code == 200, result.text
    assert result.json()["id"] == lesson["id"]
    assert result.json()["revision"] == 1
    assert api.get(path).json()["content"]["title"] == "Water"
    assert api.put(path, json=update).status_code == 409
    assert api.put(path, json={**update, "expectedRevision": 1, "minutes": 11}).status_code == 422
    assert len(api.get("/api/v1/lessons").json()["items"]) == 1
    api.cookies.clear()
    from fixtures.authenticated_client import authenticate_client

    authenticate_client(api, "user_00000000-0000-0000-0000-000000000002")
    assert api.put(path, json={**update, "expectedRevision": 1}).status_code == 404


def test_lesson_round_trip_owner_isolation_and_recovery(api, clean_mysql):
    payload = {
        "style": {"visualStyleId": "flat-vector-science"},
        "title": "Chemical bonds",
        "description": "Explain bonding with water",
        "minutes": 3,
    }
    created = api.post("/api/v1/lessons", json=payload)
    assert created.status_code == 201, created.text
    lesson = created.json()
    owner_cookie = api.cookies.get("cm_session")
    assert owner_cookie and lesson["ownerId"].startswith("user_")
    path = "/api/v1/lessons/" + lesson["id"]
    assert api.get(path).json() == lesson
    with Session(clean_mysql) as session:
        saved = SqlAlchemyStandaloneLessons(session).require_by_id(LessonId(lesson["id"]))
        assert saved.content.minutes == 3
        assert str(saved.owner_id) == lesson["ownerId"]
    assert api.get("/api/v1/lessons").json()["items"] == [lesson]
    assert api.get("/api/v1/courses").json()["items"] == []
    # Missing providers leave the draft intact for a later retry.
    failed = api.post(
        path + "/plan", json={"message": payload["description"], "expectedRevision": 0}
    )
    assert failed.status_code == 503, failed.text
    assert api.get(path).json() == lesson
    assert api.post(path + "/approve", json={"expectedRevision": 0}).status_code == 409
    api.cookies.clear()
    from fixtures.authenticated_client import authenticate_client

    authenticate_client(api, "user_00000000-0000-0000-0000-000000000002")
    assert api.get("/api/v1/lessons").json()["items"] == []
    assert api.get(path).status_code == 404
    assert (
        api.post(path + "/plan", json={"message": "Change", "expectedRevision": 0}).status_code
        == 404
    )
    # Forging the owner portion of the cookie does not grant ownership.
    api.cookies.clear()
    api.cookies.set("course_maker_owner", lesson["ownerId"] + ".forged")
    assert api.get(path).status_code == 401


@pytest.mark.parametrize("minutes", [0, 11, 3.5, True])
def test_lesson_http_duration_validation(api, minutes):
    result = api.post(
        "/api/v1/lessons",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": "Chemistry",
            "description": "Atoms",
            "minutes": minutes,
        },
    )
    assert result.status_code == 422


def test_owner_cannot_be_supplied_by_the_client(api):
    result = api.post(
        "/api/v1/lessons",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": "Chemistry",
            "description": "Atoms",
            "minutes": 3,
            "ownerId": "forged",
        },
    )
    assert result.status_code == 422
