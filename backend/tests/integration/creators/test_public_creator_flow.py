from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from fixtures.creator_app import LocalMediaStorage, create_creator_test_app

from app.courses.adapters.persistence.creators import SqlAlchemyCreators
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.domain.identifiers import CourseId, LessonId

pytestmark = pytest.mark.integration
VIDEO = "https://example.com/finished.mp4"


def test_creator_to_public_viewer_with_real_database_and_production_wiring(creator_sessions):
    storage = LocalMediaStorage()
    app = create_creator_test_app(creator_sessions, storage)
    with TestClient(app) as creator, TestClient(app) as viewer:
        identity = creator.get("/api/v1/creators/me").json()
        owner_id = identity["id"]
        photo = "data:image/png;base64,AAAA"
        saved = creator.put("/api/v1/creators/me", json={"name": "Ada Lovelace", "picture": photo})
        assert saved.status_code == 200, saved.text
        visitor_id = viewer.get("/api/v1/creators/me").json()["id"]
        assert visitor_id != owner_id
        empty_profile = viewer.get(f"/api/v1/creators/{visitor_id}")
        assert empty_profile.status_code == 200
        assert empty_profile.json()["lessons"] == []
        assert empty_profile.json()["courses"] == []
        assert (
            creator.put(
                "/api/v1/creators/me", json={"name": "Ada", "picture": "javascript:x"}
            ).status_code
            == 422
        )
        assert creator.get("/api/v1/creators/me").json()["name"] == "Ada Lovelace"
        private = creator.post(
            "/api/v1/lessons",
            json={
                "style": {"visualStyleId": "flat-vector-science"},
                "title": "Private draft",
                "description": "Private prompt",
                "minutes": 3,
            },
        ).json()
        published = creator.post(
            "/api/v1/lessons",
            json={
                "style": {"visualStyleId": "flat-vector-science"},
                "title": "Inertia",
                "description": "Creator notes",
                "minutes": 3,
            },
        ).json()
        course_response = creator.post(
            "/api/v1/courses",
            json={
                "style": {"visualStyleId": "flat-vector-science"},
                "title": "Physics",
                "description": "Learn motion",
                "duration": {"mode": "total", "hours": 1},
            },
        )
        assert course_response.status_code == 201, course_response.text
        course = course_response.json()
        assert course["ownerId"] == owner_id
        assert (
            creator.put(
                f"/api/v1/courses/{course['id']}/syllabus",
                json={
                    "chapters": [
                        {
                            "title": "Motion",
                            "summary": "Basics",
                            "lessons": [{"title": "Velocity", "topics": ["Speed"], "minutes": 3}],
                        }
                    ]
                },
            ).status_code
            == 200
        )
        # Rendered media is handed off to persistence; the animator currently produces source only.
        with creator_sessions() as db:
            lessons = SqlAlchemyStandaloneLessons(db)
            item = lessons.require_by_id(LessonId(published["id"]))
            lessons.save(replace(item, content=replace(item.content, video_url=VIDEO)))
            courses = MySqlCourseRepository(db)
            aggregate = courses.require_by_id(CourseId(course["id"]))
            nested = aggregate.chapters[0].lessons[0]
            asset_id = "asset_00000000-0000-0000-0000-000000000001"
            courses.save(
                replace(
                    aggregate,
                    chapters=(
                        replace(
                            aggregate.chapters[0],
                            lessons=(replace(nested, video_asset_id=asset_id),),
                        ),
                    ),
                )
            )
            db.commit()
        page = viewer.get(f"/api/v1/creators/{owner_id}")
        assert page.status_code == 200, page.text
        data = page.json()
        assert data["creator"] == {"id": owner_id, "name": "Ada Lovelace", "picture": photo}
        assert [ls["title"] for ls in data["lessons"]] == ["Inertia"]
        assert data["courses"][0]["title"] == "Physics"
        assert "Private prompt" not in page.text and "Creator notes" not in page.text
        assert "turns" not in page.text and "email" not in page.text
        assert viewer.get(f"/api/v1/published/lessons/{private['id']}").status_code == 404
        assert viewer.get(f"/api/v1/lessons/{published['id']}").status_code == 404
        watch = viewer.get(f"/api/v1/published/lessons/{published['id']}").json()
        assert watch["lesson"]["videoUrl"] == VIDEO
        assert watch["creator"]["id"] == owner_id
        asset_watch = viewer.get(f"/api/v1/published/lessons/{nested.id}?course_id={course['id']}")
        assert asset_watch.status_code == 200, asset_watch.text
        assert asset_watch.json()["lesson"]["videoUrl"] == "http://127.0.0.1:50120/test-video.mp4"
        assert storage.downloads == [f"courses/{course['id']}/{asset_id}"]
        # Reload through a fresh SQL session proves public identity and association persistence.
        with creator_sessions() as db:
            assert SqlAlchemyCreators(db).get_by_id(item.owner_id).name == "Ada Lovelace"
            assert MySqlCourseRepository(db).require_by_id(aggregate.id).owner_id == owner_id
        creator.put("/api/v1/creators/me", json={"name": "Ada Byron", "picture": None})
        refreshed = viewer.get(f"/api/v1/creators/{owner_id}").json()
        assert refreshed["creator"]["name"] == "Ada Byron"
        assert refreshed["creator"]["picture"] is None
        assert viewer.get("/api/v1/creators/not-a-user").status_code == 422
        assert (
            viewer.get("/api/v1/creators/user_00000000-0000-0000-0000-000000000099").status_code
            == 404
        )
