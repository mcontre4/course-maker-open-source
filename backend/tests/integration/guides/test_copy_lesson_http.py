import pytest
from fixtures.public_content import seed_public_content
from sqlalchemy.orm import Session

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"

pytestmark = pytest.mark.integration


def test_copy_http_persists_new_identity_and_enforces_owner_boundary(guide_client_factory):
    with guide_client_factory(OWNER) as owner, guide_client_factory(OTHER) as other:
        source = owner.post(
            "/api/v1/lessons",
            json={
                "title": "Rain",
                "description": "Explain rain",
                "minutes": 1,
                "style": {"visualStyleId": "flat-vector-science"},
            },
        ).json()
        path = f"/api/v1/lessons/{source['id']}"
        denied = other.post(path + "/copy", json={})
        assert denied.status_code == 404
        result = owner.post(path + "/copy", json={})
        assert result.status_code == 201
        copied = result.json()
        assert copied["id"] != source["id"]
        assert copied["ownerId"] == OWNER
        assert copied["content"]["title"] == "Rain-copy"
        assert owner.get(f"/api/v1/lessons/{copied['id']}").json() == copied
        assert other.get(f"/api/v1/lessons/{copied['id']}").status_code == 404
        assert owner.get(path).json() == source
        assert len(owner.get("/api/v1/lessons").json()["items"]) == 2


@pytest.mark.parametrize("from_course", [False, True])
def test_finished_copy_round_trips_all_media_through_real_persistence(
    guide_database, guide_client_factory, from_course
):
    with Session(guide_database) as session:
        course, lesson, _ = seed_public_content(session)
    with guide_client_factory(OTHER) as client:
        result = client.post(
            f"/api/v1/lessons/{lesson.id}/copy",
            json={"courseId": str(course.id)} if from_course else {},
        )
        assert result.status_code == 201, result.text
        copied = result.json()
        assert copied["ownerId"] == OTHER
        saved = client.get(f"/api/v1/lessons/{copied['id']}").json()
        assert saved == copied
        assert saved["content"]["animation"]["lessonId"] == copied["id"]
        assert saved["content"]["storyboard"]["lessonId"] == copied["id"]
        assert saved["content"]["alignment"]["lessonId"] == copied["id"]
        assert saved["content"]["plan"]["lessonId"] == copied["id"]


def test_copy_http_accepts_a_title_and_rejects_unusable_ones(guide_client_factory):
    with guide_client_factory(OWNER) as owner:
        source = owner.post(
            "/api/v1/lessons",
            json={
                "title": "Rain",
                "description": "Explain rain",
                "minutes": 1,
                "style": {"visualStyleId": "flat-vector-science"},
            },
        ).json()
        path = f"/api/v1/lessons/{source['id']}/copy"
        named = owner.post(path, json={"title": "  Rain, for my class  "})
        assert named.status_code == 201
        assert named.json()["content"]["title"] == "Rain, for my class"
        for title in ("", "   ", "A" * 121):
            assert owner.post(path, json={"title": title}).status_code in (400, 422)
        assert len(owner.get("/api/v1/lessons").json()["items"]) == 2
