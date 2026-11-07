from typing import Annotated

import pytest
from fakes.style import FixedVoiceCatalog, RecordingStylePlanner
from fastapi import Depends
from sqlalchemy.orm import Session

from app.courses.adapters.http.style import get_course_style, get_lesson_style, get_voices
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.style import ListVoices, UpdateCourseStyle, UpdateStandaloneStyle
from app.courses.domain.identifiers import LessonId
from app.shared.infrastructure.database import get_session

pytestmark = pytest.mark.integration


def configure(api):
    planner, voices = RecordingStylePlanner(), FixedVoiceCatalog()

    def lesson_style(session: Annotated[Session, Depends(get_session)]):
        return UpdateStandaloneStyle(
            SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session), planner, voices
        )

    def course_style(session: Annotated[Session, Depends(get_session)]):
        return UpdateCourseStyle(
            MySqlCourseRepository(session), CourseUnitOfWork(session), planner, voices
        )

    api.app.dependency_overrides.update(
        {
            get_lesson_style: lesson_style,
            get_course_style: course_style,
            get_voices: lambda: ListVoices(voices),
        }
    )
    return planner


def test_style_http_database_reload_history_ownership_and_conflicts(api, clean_mysql):
    configure(api)
    created = api.post(
        "/api/v1/lessons",
        json={
            "title": "Rainbows",
            "description": "Explain rainbows",
            "minutes": 1,
            "style": {
                "visualStyleId": "flat-vector-science",
                "description": "Playful",
                "audience": "Children aged 8–10",
            },
        },
    )
    assert created.status_code == 201, created.text
    path = "/api/v1/lessons/" + created.json()["id"]
    body = {
        "style": {
            "visualStyleId": "flat-vector-science",
            "description": "Warm",
            "voiceId": "steady",
        },
        "expectedVersion": 1,
        "generationMode": "fast",
    }
    updated = api.post(path + "/style", json=body)
    assert updated.status_code == 200, updated.text
    saved = api.get(path).json()
    assert saved["content"]["style"]["voiceId"] == "steady"
    assert saved["content"]["styleHistory"][0]["request"] == "Playful"
    # This reload also exercises recursive identifier serialization inside archived lessons.
    with Session(clean_mysql) as session:
        lesson = SqlAlchemyStandaloneLessons(session).require_by_id(LessonId(created.json()["id"]))
        assert lesson.content.previous_versions[0].id == lesson.content.id
        assert lesson.content.style.request == "Warm"
    assert api.post(path + "/style", json=body).status_code == 409
    cookies = dict(api.cookies)
    api.cookies.clear()
    from fixtures.authenticated_client import authenticate_client

    authenticate_client(api, "user_00000000-0000-0000-0000-000000000002")
    assert api.post(path + "/style", json=replace_body(body, expectedVersion=2)).status_code == 404
    api.cookies.clear()
    api.cookies.update(cookies)
    api.headers["X-CSRF-Token"] = cookies["cm_csrf"]
    assert api.post(path + "/style", json=replace_body(body, expectedVersion=-1)).status_code == 422
    assert (
        api.post(
            path + "/style",
            json=replace_body(body, style={"voiceId": "unknown"}, expectedVersion=2),
        ).status_code
        == 422
    )


def replace_body(body, **values):
    return {**body, **values}


def test_course_style_and_lesson_inheritance_survive_database(api, draft_payload, syllabus_payload):
    configure(api)
    course = api.post(
        "/api/v1/courses",
        json={
            **draft_payload,
            "style": {"visualStyleId": "flat-vector-science", "description": "Professional"},
        },
    ).json()
    path = "/api/v1/courses/" + course["id"]
    outlined = api.put(path + "/syllabus", json=syllabus_payload).json()
    lesson_id = outlined["chapters"][0]["lessons"][0]["id"]
    body = {
        "style": {"visualStyleId": "flat-vector-science", "description": "Warm"},
        "expectedVersion": 0,
        "generationMode": "fast",
    }
    override = api.post(path + f"/lessons/{lesson_id}/style", json=body)
    assert override.status_code == 200, override.text
    assert override.json()["chapters"][0]["lessons"][0]["style"]["request"] == "Warm"
    changed = api.post(path + "/style", json={**body, "expectedVersion": 1})
    assert changed.status_code == 200, changed.text
    assert api.get(path).json()["style"]["version"] == 2  # pending input becomes resolved version 1
    inherited = api.post(
        path + f"/lessons/{lesson_id}/style", json={"style": None, "expectedVersion": 1}
    )
    assert inherited.status_code == 200, inherited.text
    assert api.get(path).json()["chapters"][0]["lessons"][0]["style"] is None


def test_voice_catalog_is_authenticated_and_does_not_expose_keys(api):
    configure(api)
    response = api.get("/api/v1/voices?search=calm")
    assert response.status_code == 200 and response.json()["items"][0]["id"] == "steady"
    api.headers.pop("Authorization")
    api.cookies.clear()
    assert api.get("/api/v1/voices").status_code == 401


def test_draft_style_edits_persist_without_calling_providers(api, draft_payload):
    planner = configure(api)
    for endpoint, details, nested in (
        (
            "lessons",
            {
                "style": {"visualStyleId": "flat-vector-science"},
                "title": "Rainbows",
                "description": "Explain colors",
                "minutes": 1,
            },
            True,
        ),
        ("courses", draft_payload, False),
    ):
        created = api.post(
            "/api/v1/" + endpoint,
            json={
                **details,
                "style": {
                    "visualStyleId": "flat-vector-science",
                    "description": "Playful",
                    "audience": "Children",
                },
            },
        )
        assert created.status_code == 201, created.text
        saved = created.json()
        path = "/api/v1/" + endpoint + "/" + saved["id"]
        changed = api.put(
            path,
            json={
                **details,
                **({"expectedRevision": saved["revision"]} if nested else {}),
                "style": {
                    "visualStyleId": "flat-vector-science",
                    "description": "Warm and reassuring",
                    "audience": "Beginners",
                },
            },
        )
        assert changed.status_code == 200, changed.text
        loaded = api.get(path).json()
        profile = loaded["content"]["style"] if nested else loaded["style"]
        assert profile["request"] == "Warm and reassuring"
        assert profile["audience"] == "Beginners"
        assert profile["resolved"] is False
        assert profile["version"] == 2
    assert planner.calls == []
