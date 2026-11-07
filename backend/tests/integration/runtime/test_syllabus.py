import json
from dataclasses import asdict, replace

import pytest
from fixtures.syllabus import curriculum
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.courses.adapters.http.syllabus import get_generator
from app.courses.adapters.persistence.conversations import (
    SqlAlchemySyllabusConversations,
    SyllabusConversationRecord,
)
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.composition import build_syllabus_services
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import CourseId
from app.courses.ports.syllabus_agent import SyllabusAgentResponse, SyllabusConversation

pytestmark = pytest.mark.integration


class ContextAwareAgent:
    def __init__(self):
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        plan = curriculum()
        chapter = plan.chapters[0]
        plan = replace(
            plan,
            chapters=(
                replace(
                    chapter,
                    lessons=(
                        chapter.lessons[0],
                        replace(chapter.lessons[1], week=2),
                    ),
                ),
            ),
        )
        if request.history_json != "[]":
            context = {"course": asdict(request.course)}
            persisted = context["course"]["chapters"][0]
            first, second = plan.chapters[0].lessons
            plan = replace(
                plan,
                chapters=(
                    replace(
                        plan.chapters[0],
                        chapter_id=persisted["id"],
                        lessons=(
                            replace(
                                first,
                                lesson_id=persisted["lessons"][0]["id"],
                                title="Named values",
                                chapter_id=persisted["id"],
                            ),
                            replace(
                                second,
                                lesson_id=persisted["lessons"][1]["id"],
                                chapter_id=persisted["id"],
                                prerequisites=(persisted["lessons"][0]["id"],),
                            ),
                        ),
                    ),
                ),
                required_topic_coverage=tuple(
                    replace(item, lesson_ids=(persisted["lessons"][0]["id"],))
                    for item in plan.required_topic_coverage
                ),
            )
        return SyllabusAgentResponse("Updated", plan, json.dumps([asdict(plan)]))


def test_http_two_requests_resume_after_new_repository_instance(api, draft_payload, clean_mysql):
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    path = f"/api/v1/courses/{course_id}/syllabus"
    agent = ContextAwareAgent()

    # Inject just the outgoing API boundary; use the real database and application wiring.
    def generator():
        with Session(clean_mysql) as session:
            yield build_syllabus_services(session, agent)[0]

    api.app.dependency_overrides[get_generator] = generator
    assert api.get(path + "/session").json()["revision"] == 0
    first = api.post(
        path + "/generate", json={"message": "  Teach Python  ", "expectedRevision": 0}
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["course"]["chapters"][0]["lessons"][0]["id"]
    second = api.post(
        path + "/generate", json={"message": "Rename variables", "expectedRevision": 1}
    )
    assert second.status_code == 200, second.text
    assert second.json()["course"]["chapters"][0]["lessons"][0]["id"] == first_id
    saved = api.get(path + "/session").json()
    assert saved["revision"] == 2 and len(saved["turns"]) == 2
    assert saved["turns"][0]["user"] == "  Teach Python  "
    assert saved["curriculum"]["chapters"][0]["lessons"][0]["lesson_id"] == first_id
    assert saved["curriculum"]["required_topic_coverage"]
    assert saved["sessionId"] == course_id
    assert "history_json" not in saved
    assert agent.requests[0].message == "  Teach Python  "
    assert agent.requests[1].history_json != "[]"
    assert (
        api.get(f"/api/v1/courses/{course_id}").json()["chapters"][0]["lessons"][0]["title"]
        == "Named values"
    )
    stale = api.post(path + "/generate", json={"message": "Old edit", "expectedRevision": 1})
    assert stale.status_code == 409
    assert len(agent.requests) == 2
    assert api.delete(f"/api/v1/courses/{course_id}").status_code == 204
    with Session(clean_mysql) as session:
        assert (
            SqlAlchemySyllabusConversations(session).get_by_course_id(CourseId(course_id)) is None
        )


def test_missing_keys_and_invalid_transport(api, draft_payload):
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    path = f"/api/v1/courses/{course_id}/syllabus/generate"
    for body in [
        {},
        {"message": " "},
        {"message": "Hi", "history": []},
        {"message": "x" * 20001},
        {"message": "Hi", "expectedRevision": -1},
    ]:
        assert api.post(path, json=body).status_code == 422
    assert api.post(path, json={"message": "Teach Python"}).status_code == 503


def test_conversation_compare_and_swap_and_rollback(api, draft_payload, clean_mysql):
    course_id = CourseId(api.post("/api/v1/courses", json=draft_payload).json()["id"])
    state = SyllabusConversation(str(course_id), revision=1, history_json="history")
    with Session(clean_mysql) as session:
        repository = SqlAlchemySyllabusConversations(session)
        repository.save(state, 0)
        session.commit()
    with Session(clean_mysql) as session:
        repository = SqlAlchemySyllabusConversations(session)
        assert repository.get_by_course_id(course_id) == state
        with pytest.raises(CourseConflict):
            repository.save(state, 0)
        session.rollback()
        with pytest.raises(CourseConflict):
            repository.save(replace(state, revision=3), 2)
        session.rollback()
        repository.save(replace(state, revision=2), 1)
        session.rollback()
    with Session(clean_mysql) as session:
        assert SqlAlchemySyllabusConversations(session).get_by_course_id(course_id) == state


def test_syllabus_responses_have_explicit_openapi_contracts(api):
    paths = api.get("/openapi.json").json()["paths"]
    response = paths["/api/v1/courses/{course_id}/syllabus/generate"]["post"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith(
        "/GenerateSyllabusView"
    )


def test_course_is_serialized_during_syllabus_write(api, draft_payload, clean_mysql):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    course_id = CourseId(api.post("/api/v1/courses", json=draft_payload).json()["id"])
    started = Event()

    def competing_change():
        with Session(clean_mysql) as session:
            started.set()
            return MySqlCourseRepository(session).require_for_syllabus_change(course_id)

    with Session(clean_mysql) as session:
        course = MySqlCourseRepository(session).require_for_syllabus_change(course_id)
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(competing_change)
            try:
                assert started.wait(timeout=5)
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.2)
            finally:
                session.rollback()
            assert future.result(timeout=5) == course


def test_conversation_revision_constraints_are_enforced(api, draft_payload, clean_mysql):
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    with Session(clean_mysql) as session:
        repository = SqlAlchemySyllabusConversations(session)
        with pytest.raises(CourseError):
            repository.save(SyllabusConversation(course_id, revision=2), expected_revision=0)
        session.add(
            SyllabusConversationRecord(
                course_id=course_id, revision=0, history_json="[]", curriculum_json=None, turns=[]
            )
        )
        with pytest.raises(OperationalError) as error:
            session.commit()
        assert error.value.orig.args[0] == 3819
        session.rollback()
        assert repository.get_by_course_id(CourseId(course_id)) is None


def test_missing_course_is_not_misreported_as_conversation_conflict(clean_mysql):
    course_id = CourseId("course_00000000-0000-0000-0000-000000999999")
    with Session(clean_mysql) as session:
        with pytest.raises(CourseNotFound):
            MySqlCourseRepository(session).require_for_syllabus_change(course_id)
        with pytest.raises(IntegrityError):
            SqlAlchemySyllabusConversations(session).save(
                SyllabusConversation(str(course_id), revision=1), expected_revision=0
            )
