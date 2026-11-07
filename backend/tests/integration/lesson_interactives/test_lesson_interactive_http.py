from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from time import monotonic, sleep

import pytest
from fakes.lesson_interactive import BlockingInteractiveAgent, RecordingInteractiveAgent
from fastapi.testclient import TestClient
from fixtures.lesson_interactive_app import (
    HEADERS,
    create_interactive_lesson,
    interactive_test_app,
)
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.lesson_interactive import (
    LessonInteractiveRecord,
    SqlAlchemyInteractiveLessons,
    SqlAlchemyLessonInteractives,
)
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.standalone import (
    SqlAlchemyStandaloneLessons,
    StandaloneLessonRecord,
)
from app.courses.domain.course import Course
from app.courses.domain.duration import Duration
from app.courses.domain.identifiers import ChapterId, CourseId, LessonId
from app.courses.domain.lesson_interactive import InteractiveId
from app.courses.domain.syllabus import Chapter

pytestmark = pytest.mark.integration


def finished(client, path):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200, response.text
        item = response.json()
        if item["build"] is None:
            assert item["failure"] is None, item
            return item
        sleep(0.02)
    pytest.fail("The interactive did not finish")


def publish_lesson(engine, lesson_id):
    with Session(engine) as session:
        lessons = SqlAlchemyStandaloneLessons(session)
        lesson = lessons.require_by_id(LessonId(lesson_id))
        lessons.save(
            replace(
                lesson, content=replace(lesson.content, video_url="https://example.com/video.mp4")
            )
        )
        session.commit()


def test_http_background_lifecycle_published_isolation_and_restart(interactive_database):
    engine, agent = interactive_database, RecordingInteractiveAgent()
    with ThreadPoolExecutor(max_workers=2) as workers:
        app = interactive_test_app(engine, agent, workers)
        with TestClient(app, headers=HEADERS) as owner:
            lesson_id = create_interactive_lesson(owner)
            root = f"/api/v1/lessons/{lesson_id}/interactives"
            assert owner.get(root).json() == {"items": []}
            before = owner.get(f"/api/v1/lessons/{lesson_id}").json()
            created = owner.post(root, json={"brief": "  A pendulum  ", "generationMode": "fast"})
            assert created.status_code == 201, created.text
            path = root + "/" + created.json()["id"]
            item = finished(owner, path)
            assert item["brief"] == "A pendulum" and item["currentVersion"] == 1
            assert item["publishedHtml"] is None and len(item["prompts"]) == 2
            assert isinstance(item["updatedAt"], str) and "token" not in str(item)
            assert owner.get(f"/api/v1/lessons/{lesson_id}").json() == before
            assert "html" not in item["versions"][0]
            saved = owner.patch(
                path,
                json={
                    "title": " My lab ",
                    "goal": " Explore ",
                    "prompts": [" Try it "],
                    "expectedRevision": item["revision"],
                },
            )
            assert saved.status_code == 200, saved.text
            item = saved.json()
            assert item["title"] == "My lab" and item["prompts"] == ["Try it"]
            assert (
                owner.patch(
                    path,
                    json={
                        "title": "Stale",
                        "goal": "",
                        "prompts": [],
                        "expectedRevision": item["revision"] - 1,
                    },
                ).status_code
                == 409
            )
            item = owner.put(path + "/published", json={"version": 1}).json()
            public_path = f"/api/v1/published/lessons/{lesson_id}/interactives"
            assert owner.get(public_path).status_code == 404
            publish_lesson(engine, lesson_id)
            changed = owner.post(
                path + "/changes",
                json={"instruction": "Change gravity", "expectedRevision": item["revision"]},
            )
            assert changed.status_code == 200, changed.text
            item = finished(owner, path)
            assert item["currentVersion"] == 2 and item["publishedVersion"] == 1
            assert item["title"] == "My lab" and item["goal"] == "Explore"
            public = owner.get(public_path).json()["items"][0]
            assert public["html"] == item["publishedHtml"] and public["version"] == 1
            assert set(public) == {"id", "lessonId", "version", "title", "goal", "prompts", "html"}
            item = owner.post(
                path + "/versions/1/restore", json={"expectedRevision": item["revision"]}
            ).json()
            assert item["currentVersion"] == 1 and len(item["versions"]) == 2
            owner.post(
                path + "/changes",
                json={"instruction": "Add reset", "expectedRevision": item["revision"]},
            )
            item = finished(owner, path)
            assert item["currentVersion"] == 3
            copied = owner.post(f"/api/v1/lessons/{lesson_id}/copy", json={})
            assert copied.status_code == 201, copied.text
            copies = owner.get(f"/api/v1/lessons/{copied.json()['id']}/interactives").json()[
                "items"
            ]
            assert copies[0]["currentVersion"] == 3 and copies[0]["publishedVersion"] == 1
            assert copies[0]["id"] != item["id"]
            owner_cookies = dict(owner.cookies)
        with TestClient(app) as public_client:
            assert public_client.get(root).status_code == 401
            assert public_client.get(public_path).json()["items"][0]["version"] == 1
        with TestClient(app, headers=HEADERS) as other:
            assert other.get(root).status_code == 404
            assert other.post(path + "/build/cancel").status_code == 404
            assert other.delete(path).status_code == 404
            copied = other.post(f"/api/v1/lessons/{lesson_id}/copy", json={})
            assert copied.status_code == 201, copied.text
            copies = other.get(f"/api/v1/lessons/{copied.json()['id']}/interactives").json()[
                "items"
            ]
            assert len(copies[0]["versions"]) == 1 and copies[0]["publishedVersion"] == 1
        with TestClient(interactive_test_app(engine, agent, workers), headers=HEADERS) as reopened:
            reopened.cookies.update(owner_cookies)
            assert reopened.get(path).json() == item
            assert reopened.put(path + "/published", json={"version": None}).status_code == 200
            assert reopened.get(public_path).json() == {"items": []}
            assert reopened.delete(path).status_code == 204
            assert reopened.get(path).status_code == 404


def test_cancel_retry_and_optimistic_concurrency_while_agent_runs(interactive_database):
    engine, agent = interactive_database, BlockingInteractiveAgent()
    with ThreadPoolExecutor(max_workers=2) as workers:
        app = interactive_test_app(engine, agent, workers)
        with TestClient(app, headers=HEADERS) as owner:
            lesson_id = create_interactive_lesson(owner)
            root = f"/api/v1/lessons/{lesson_id}/interactives"
            item = owner.post(root, json={"brief": "A lab"}).json()
            path = root + "/" + item["id"]
            try:
                assert agent.started.wait(timeout=5)
                assert (
                    owner.post(
                        path + "/changes",
                        json={"instruction": "Race", "expectedRevision": item["revision"]},
                    ).status_code
                    == 409
                )
                cancelled = owner.post(path + "/build/cancel").json()
                assert cancelled["build"] is None and "cancelled" in cancelled["failure"]["message"]
                assert isinstance(cancelled["updatedAt"], str)
                retried = owner.post(path + "/build/retry")
                assert retried.status_code == 200, retried.text
                assert retried.json()["failure"] is None
            finally:
                agent.release.set()
            complete = finished(owner, path)
            assert len(complete["versions"]) == 1 and complete["currentVersion"] == 1


def test_details_saved_during_first_build_survive_worker_session(interactive_database):
    engine, agent = interactive_database, BlockingInteractiveAgent()
    with (
        ThreadPoolExecutor(max_workers=2) as workers,
        TestClient(interactive_test_app(engine, agent, workers), headers=HEADERS) as owner,
    ):
        lesson_id = create_interactive_lesson(owner)
        root = f"/api/v1/lessons/{lesson_id}/interactives"
        created = owner.post(root, json={"brief": "A lab"}).json()
        path = root + "/" + created["id"]
        try:
            assert agent.started.wait(timeout=5)
            saved = owner.patch(
                path,
                json={
                    "title": "Creator title",
                    "goal": "Creator goal",
                    "prompts": ["Creator challenge"],
                    "expectedRevision": created["revision"],
                },
            )
            assert saved.status_code == 200, saved.text
        finally:
            agent.release.set()
        complete = finished(owner, path)
        assert complete["title"] == "Creator title" and complete["goal"] == "Creator goal"
        assert complete["prompts"] == ["Creator challenge"]
        assert complete["currentVersion"] == 1
        assert "detailsCustomized" not in complete


def test_validation_limit_order_and_database_constraints(interactive_database):
    engine, agent = interactive_database, RecordingInteractiveAgent()
    with (
        ThreadPoolExecutor(max_workers=2) as workers,
        TestClient(interactive_test_app(engine, agent, workers), headers=HEADERS) as owner,
    ):
        lesson_id = create_interactive_lesson(owner)
        root = f"/api/v1/lessons/{lesson_id}/interactives"
        for brief in ("", " ", "x" * 2001):
            assert owner.post(root, json={"brief": brief}).status_code == 422
        items = [owner.post(root, json={"brief": "A lab"}).json() for _ in range(10)]
        assert owner.post(root, json={"brief": "Too many"}).status_code == 409
        path = root + "/" + items[0]["id"]
        item = finished(owner, path)
        for details in (
            {"title": " "},
            {"title": "a" * 81},
            {"goal": "g" * 201},
            {"prompts": [""]},
            {"prompts": ["p" * 161]},
            {"prompts": ["p"] * 7},
        ):
            payload = {
                "title": "Title",
                "goal": "",
                "prompts": [],
                "expectedRevision": item["revision"],
            } | details
            assert owner.patch(path, json=payload).status_code == 422
        assert (
            owner.post(
                path + "/changes",
                json={"instruction": "x" * 1001, "expectedRevision": item["revision"]},
            ).status_code
            == 422
        )
        assert owner.put(path + "/published", json={"version": True}).status_code == 422
        assert owner.put(path + "/published", json={"version": 99}).status_code == 404
        ids = [i["id"] for i in reversed(items)]
        ordered = owner.put(root + "/order", json={"ids": ids})
        assert ordered.status_code == 200, ordered.text
        assert [i["id"] for i in ordered.json()["items"]] == ids
        assert [i["id"] for i in owner.get(root).json()["items"]] == ids
        assert owner.put(root + "/order", json={"ids": [ids[0]] * 10}).status_code == 422
        assert owner.delete(path).status_code == 204
        assert owner.post(root, json={"brief": "Slot reused"}).status_code == 201
    # The FK removes all versions and builds with a deleted standalone lesson.
    with Session(engine) as session:
        session.execute(
            delete(StandaloneLessonRecord).where(StandaloneLessonRecord.id == lesson_id)
        )
        session.commit()
        assert not SqlAlchemyLessonInteractives(session).list_by_lesson_id(LessonId(lesson_id))


def test_course_lesson_ownership_copy_and_removal(interactive_database):
    engine, agent = interactive_database, RecordingInteractiveAgent()
    with (
        ThreadPoolExecutor(max_workers=2) as workers,
        TestClient(interactive_test_app(engine, agent, workers), headers=HEADERS) as owner,
    ):
        standalone_id = create_interactive_lesson(owner)
        with Session(engine) as session:
            source = SqlAlchemyStandaloneLessons(session).require_by_id(LessonId(standalone_id))
            course_id = CourseId("course_00000000-0000-0000-0000-000000000099")
            lesson_id = LessonId("lesson_00000000-0000-0000-0000-000000000098")
            content = replace(
                source.content, id=lesson_id, video_url="https://example.com/video.mp4"
            )
            course = Course(
                course_id,
                "Course",
                "Course description",
                Duration("total", hours=1),
                chapters=(
                    Chapter(
                        ChapterId("chapter_00000000-0000-0000-0000-000000000097"),
                        "Chapter",
                        "",
                        (content,),
                    ),
                ),
                owner_id=str(source.owner_id),
            )
            MySqlCourseRepository(session).add(course)
            session.commit()
        root = f"/api/v1/lessons/{lesson_id}/interactives"
        created = owner.post(root, json={"brief": "A course lab"})
        assert created.status_code == 201, created.text
        path = root + "/" + created.json()["id"]
        item = finished(owner, path)
        assert agent.calls[-1].description == "Course description"
        assert owner.put(path + "/published", json={"version": 1}).status_code == 200
        assert owner.get(f"/api/v1/published/lessons/{lesson_id}/interactives").json()["items"]
        with TestClient(owner.app, headers=HEADERS) as other:
            assert other.get(root).status_code == 404
            assert other.post(root, json={"brief": "Unauthorized"}).status_code == 404
        copied = owner.post(f"/api/v1/lessons/{lesson_id}/copy", json={"courseId": str(course_id)})
        assert copied.status_code == 201, copied.text
        assert owner.get(f"/api/v1/lessons/{copied.json()['id']}/interactives").json()["items"]
        with Session(engine) as session:
            lessons = SqlAlchemyInteractiveLessons(session)
            assert lessons.require_by_id(lesson_id).course_id == str(course_id)
            repository = MySqlCourseRepository(session)
            course = repository.require_by_id(course_id)
            repository.save(replace(course, chapters=()))
            session.commit()
            assert session.get(LessonInteractiveRecord, item["id"]) is None
            assert (
                SqlAlchemyLessonInteractives(session).get_by_id(InteractiveId(item["id"])) is None
            )
        assert owner.get(root).status_code == 404


def test_competing_creates_share_the_lesson_limit(interactive_database):
    engine, agent = interactive_database, RecordingInteractiveAgent()
    with ThreadPoolExecutor(max_workers=2) as workers:
        app = interactive_test_app(engine, agent, workers)
        with TestClient(app, headers=HEADERS) as owner:
            lesson_id = create_interactive_lesson(owner)
            root = f"/api/v1/lessons/{lesson_id}/interactives"
            for _ in range(9):
                assert owner.post(root, json={"brief": "Existing lab"}).status_code == 201
            cookies = dict(owner.cookies)

            def create_one():
                with TestClient(app, headers=HEADERS) as competing:
                    competing.cookies.update(cookies)
                    return competing.post(root, json={"brief": "Competing lab"}).status_code

            with ThreadPoolExecutor(max_workers=2) as requests:
                results = list(requests.map(lambda _: create_one(), range(2)))
            assert sorted(results) == [201, 409]
            assert len(owner.get(root).json()["items"]) == 10
