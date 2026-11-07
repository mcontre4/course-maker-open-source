from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from fixtures.creator_app import LocalMediaStorage, create_creator_test_app
from fixtures.public_content import OWNER, seed_public_content

from app.courses.adapters.persistence.creators import SqlAlchemyCreators
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.domain.identifiers import CourseId

pytestmark = pytest.mark.integration


def test_search_ranks_exact_course_lesson_names_before_limiting(creator_sessions):
    with creator_sessions() as session:
        newest, _, _ = seed_public_content(session)
        repository = MySqlCourseRepository(session)
        older = repository.require_by_id(CourseId("course_00000000-0000-0000-0000-000000000099"))
        lesson = older.chapters[0].lessons[0]
        repository.save(older._replace_lesson(replace(lesson, title="Café algebra")))
        repository.save(replace(newest, title="Café algebra basics"))
        session.commit()
    app = create_creator_test_app(creator_sessions, LocalMediaStorage())
    with TestClient(app) as viewer:
        response = viewer.get(
            "/api/v1/published/discovery", params={"q": "CAFE algebra", "limit": 1}
        )
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["courses"]] == [str(older.id)]
        assert response.json()["courses"][0]["lessons"][0]["title"] == "Café algebra"


@pytest.mark.parametrize("query", ["older", "  oLdEr   public  ", "OLDER PUBLIC COURSE"])
def test_search_finds_older_matches_before_applying_limit(creator_sessions, query):
    with creator_sessions() as session:
        seed_public_content(session)
    app = create_creator_test_app(creator_sessions, LocalMediaStorage())
    with TestClient(app) as viewer:
        response = viewer.get("/api/v1/published/discovery", params={"q": query, "limit": 1})
        assert response.status_code == 200, response.text
        data = response.json()
        assert [item["title"] for item in data["courses"]] == ["Older public course"]
        if "course" not in query.lower():
            assert [item["title"] for item in data["lessons"]] == ["Older public lesson"]
        else:
            assert data["lessons"] == []
        assert "Private creator notes" not in response.text


def test_search_includes_published_course_lessons_and_hides_drafts(creator_sessions):
    with creator_sessions() as session:
        course, _, draft = seed_public_content(session)
    app = create_creator_test_app(creator_sessions, LocalMediaStorage())
    with TestClient(app) as viewer:
        title = course.chapters[0].lessons[0].title
        response = viewer.get("/api/v1/published/discovery", params={"q": title.upper()})
        assert response.status_code == 200, response.text
        assert str(course.id) in [item["id"] for item in response.json()["courses"]]
        for query in [draft.title, "Unfinished hidden course", "Private creator notes", "no-match"]:
            assert viewer.get("/api/v1/published/discovery", params={"q": query}).json() == {
                "courses": [],
                "lessons": [],
            }
        assert viewer.get("/api/v1/published/discovery", params={"q": "a" * 201}).status_code == 422


def test_newest_public_content_filters_drafts_before_limiting(creator_sessions):
    with creator_sessions() as session:
        course, generated, draft = seed_public_content(session)
    app = create_creator_test_app(creator_sessions, LocalMediaStorage())
    with TestClient(app) as viewer:
        response = viewer.get("/api/v1/published/discovery")
        assert response.status_code == 200, response.text
        data = response.json()
        assert [item["title"] for item in data["lessons"]] == [
            "Newest public lesson",
            "Older public lesson",
        ]
        assert [item["title"] for item in data["courses"]] == [
            "Newest public course",
            "Older public course",
        ]
        assert "Private creator notes" not in response.text
        limited = viewer.get("/api/v1/published/discovery?limit=1").json()
        assert len(limited["lessons"]) == len(limited["courses"]) == 1
        assert limited["lessons"][0]["id"] == str(generated.id)
        assert limited["courses"][0]["id"] == str(course.id)
        assert viewer.get("/api/v1/published/discovery?limit=0").status_code == 422
        assert viewer.get(f"/api/v1/published/lessons/{draft.id}/video").status_code == 404
        page = viewer.get(f"/api/v1/creators/{OWNER}").json()
        assert str(generated.id) in [item["id"] for item in page["lessons"]]
        watch = viewer.get(f"/api/v1/published/lessons/{generated.id}").json()
        assert watch["lesson"]["videoUrl"].endswith(f"/{generated.id}/video")
        nested = viewer.get(
            f"/api/v1/published/lessons/{generated.id}?course_id={course.id}"
        ).json()
        assert nested["lesson"]["videoUrl"].endswith(f"?course_id={course.id}")
    with creator_sessions() as session:
        repository = SqlAlchemyCreators(session)
        assert repository.latest_lessons(1)[0].content.id == generated.id
        assert repository.latest_courses(1)[0].id == course.id


def test_creation_time_migration_preserves_existing_content(creator_database, creator_sessions):
    from pathlib import Path
    from runpy import run_path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    with creator_sessions() as session:
        seed_public_content(session)
    migration = run_path(
        str(Path(__file__).parents[3] / "migrations/versions/0008_content_created_at.py")
    )
    with creator_database.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                migration["downgrade"]()
                migration["upgrade"]()
            for table in ("courses", "standalone_lessons"):
                count = connection.scalar(
                    text(f"SELECT COUNT(*) FROM {table} WHERE created_at IS NOT NULL")
                )
                assert count == 3
        finally:
            transaction.rollback()
