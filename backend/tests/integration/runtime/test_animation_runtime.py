from pathlib import Path
from typing import Annotated

import pytest
from fakes.animator import RecordingAnimator
from fakes.courses import InMemoryCourses, RecordingUnitOfWork
from fastapi import Depends
from fixtures.animation import animation_inputs
from fixtures.syllabus import COURSE_ID, LESSON_ID
from sqlalchemy.orm import Session

from app.courses.adapters.http.animation import get_animation_generator
from app.courses.adapters.persistence.conversations import SqlAlchemySyllabusConversations
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.adapters.storage.speech import LocalSpeechArtifacts
from app.courses.application.generate_animation import GenerateAnimation
from app.courses.ports.animator import AnimationChangeRequest, StoryboardChangeRequired
from app.courses.ports.syllabus_agent import SyllabusConversation
from app.shared.infrastructure.database import get_session

pytestmark = pytest.mark.integration


def test_animation_http_database_retrieval_and_change_request(api, clean_mysql):
    inputs, course, curriculum, _ = animation_inputs()
    with Session(clean_mysql) as session:
        MySqlCourseRepository(session).add(course)
        session.flush()
        SqlAlchemySyllabusConversations(session).save(
            SyllabusConversation(COURSE_ID, 1, curriculum=curriculum), 0
        )
        session.commit()
    artifacts = LocalSpeechArtifacts(Path(api.app.state.settings.speech_local_directory))
    for scene, audio in zip(inputs.alignment.scenes, inputs.audio, strict=True):
        artifacts.write(scene.audio_key, audio, "audio/wav")
    uow = RecordingUnitOfWork(InMemoryCourses())
    uow.exited = True
    animator = RecordingAnimator(uow)

    def generator(session: Annotated[Session, Depends(get_session)]):
        return GenerateAnimation(
            MySqlCourseRepository(session),
            SqlAlchemySyllabusConversations(session),
            animator,
            artifacts,
            CourseUnitOfWork(session),
        )

    api.app.dependency_overrides[get_animation_generator] = generator
    path = f"/api/v1/courses/{COURSE_ID}"
    result = api.post(
        path + "/animations/generate",
        json={
            "lessonId": LESSON_ID,
            "visualStyle": "Readable diagrams",
        },
    )
    assert result.status_code == 200, result.text
    animation = result.json()["chapters"][0]["lessons"][0]["animation"]
    assert animation["status"] == "animation_ready"
    with Session(clean_mysql) as session:
        saved = MySqlCourseRepository(session).require_by_id(course.id).lesson(LESSON_ID)
        assert saved.animation.input_hash == "a" * 64
        assert saved.alignment == inputs.alignment
    assert api.get(path + f"/lessons/{LESSON_ID}").json()["animation"] == animation
    animator.error = StoryboardChangeRequired(
        AnimationChangeRequest(("s01",), "Missing trusted data", "Supply approved coordinates")
    )
    change = api.post(
        path + "/animations/generate",
        json={
            "lessonId": LESSON_ID,
            "visualStyle": "Geographic map",
        },
    )
    assert change.status_code == 409
    assert change.json()["change_request"]["requested_change"] == "Supply approved coordinates"
    assert api.post(path + "/animations/generate", json={"lessonId": LESSON_ID}).status_code == 422
    api.headers.pop("Authorization")
    api.cookies.clear()
    assert api.post(path + "/animations/generate", json={}).status_code == 401
