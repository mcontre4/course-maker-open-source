from dataclasses import replace
from typing import Annotated

import pytest
from fastapi import Depends
from fixtures.public_content import seed_public_content
from sqlalchemy.orm import Session

from app.courses.adapters.http.lesson_video import get_standalone_video_reader
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.lesson_video import GetStandaloneLessonVideo
from app.courses.domain.identifiers import LessonId
from app.shared.infrastructure.database import get_session

pytestmark = pytest.mark.integration


def test_script_edit_round_trip_keeps_previous_media_and_enforces_revisions(
    guide_client, guide_database, guide_client_factory
):
    with Session(guide_database) as session:
        _, lesson, _ = seed_public_content(session)
    path = f"/api/v1/lessons/{lesson.id}"
    before = guide_client.get(path).json()
    narrations = [s["narrationText"] for s in before["content"]["storyboard"]["scenes"]]
    narrations[0] = "An updated explanation. " + narrations[0]
    body = {"expectedRevision": before["revision"], "narrations": narrations}
    result = guide_client.put(path + "/script", json=body)
    assert result.status_code == 200, result.text
    updated = result.json()
    assert updated["content"]["animation"] is None
    assert updated["content"]["alignment"] is None
    assert updated["playbackContent"]["animation"] == before["content"]["animation"]
    assert guide_client.get(path).json() == updated
    with Session(guide_database) as session:
        saved = SqlAlchemyStandaloneLessons(session).require_by_id(LessonId(str(lesson.id)))
        assert saved.content.storyboard.scenes[0].narration_text == narrations[0].strip()
        assert saved.content.previous_versions[-1].animation == lesson.animation
    assert guide_client.put(path + "/script", json=body).status_code == 409
    body["expectedRevision"] = updated["revision"]
    assert guide_client.put(path + "/script", json={**body, "narrations": []}).status_code == 422
    assert guide_client.get(path).json() == updated
    with guide_client_factory("user_00000000-0000-0000-0000-000000000002") as other:
        assert other.put(path + "/script", json=body).status_code == 404


def test_previous_video_is_served_by_its_saved_hash_after_an_outline_edit(
    guide_client, guide_database
):
    with Session(guide_database) as session:
        _, lesson, _ = seed_public_content(session)
        repo = SqlAlchemyStandaloneLessons(session)
        before = repo.require_by_id(lesson.id)
        changed = before.edit_outline(
            replace(before.content.plan, required_facts=("Updated fact",))
        )
        repo.save(changed)
        session.commit()
    observed = []

    class VideoPort:
        def read(self, project):
            observed.append(project)
            return b"saved-video"

    def reader(session: Annotated[Session, Depends(get_session)]):
        return GetStandaloneLessonVideo(
            SqlAlchemyStandaloneLessons(session), VideoPort(), CourseUnitOfWork(session)
        )

    guide_client.app.dependency_overrides[get_standalone_video_reader] = reader
    from app.courses.adapters.http.lesson_video import router

    guide_client.app.include_router(router)
    path = f"/api/v1/lessons/{lesson.id}/video?v={lesson.animation.output_hash}"
    result = guide_client.get(path, headers={"Range": "bytes=0-4"})
    assert result.status_code == 206, result.text
    assert result.content == b"saved"
    assert observed == [lesson.animation]
    assert guide_client.get(path.replace(lesson.animation.output_hash, "f" * 64)).status_code == 409
