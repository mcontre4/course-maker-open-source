import json
from contextlib import contextmanager
from dataclasses import asdict, replace
from typing import Annotated

import httpx
import pytest
from fastapi import Depends
from fixtures.elevenlabs import elevenlabs_server
from fixtures.lesson_plan import lesson_plan
from fixtures.storyboard import storyboard
from fixtures.syllabus import COURSE_ID, LESSON_ID, make_planned_course
from sqlalchemy.orm import Session

from app.courses.adapters.ai.elevenlabs import ElevenLabsSpeech
from app.courses.adapters.http.speech import get_speech_generator
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.generate_speech import GenerateSpeech
from app.courses.domain.identifiers import CourseId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.storyboard import StoryboardGeneration
from app.main import create_app
from app.shared.infrastructure.database import get_session

pytestmark = pytest.mark.integration


def seed(engine, scene_count=2):
    draft, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    usage = PlanGeneration("test", 1, 0, 1)
    board = storyboard(plan)
    if scene_count == 3:
        board = replace(
            board,
            scenes=tuple(
                replace(board.scenes[0], scene_id=f"s{i + 1:02}", target_duration_sec=200)
                for i in range(3)
            ),
        )
    course = (
        draft.approve()
        .plan_lesson(LESSON_ID, plan, usage)
        .storyboard_lesson(
            LESSON_ID, board, StoryboardGeneration(usage, "a" * 64, "b" * 64, "v1", None)
        )
    )
    with Session(engine) as session:
        MySqlCourseRepository(session).add(course)
        session.commit()
    return board


@contextmanager
def provider_override(api, *, invalid=None, chunk_durations=None):
    production = api.app.dependency_overrides[get_speech_generator]
    with (
        elevenlabs_server(invalid=invalid, chunk_durations=chunk_durations) as (url, calls),
        httpx.Client(base_url=url) as client,
    ):
        synthesizer = ElevenLabsSpeech(client, "test-secret")
        _, artifacts, settings, gap = api.app.state.resources.speech

        def generator(session: Annotated[Session, Depends(get_session)]):
            return GenerateSpeech(
                MySqlCourseRepository(session),
                synthesizer,
                artifacts,
                settings,
                CourseUnitOfWork(session),
                gap,
            )

        api.app.dependency_overrides[get_speech_generator] = generator
        try:
            yield calls
        finally:
            api.app.dependency_overrides[get_speech_generator] = production


def test_http_to_provider_files_database_and_fresh_app(api, clean_mysql):
    board = seed(clean_mysql)
    path = f"/api/v1/courses/{COURSE_ID}"
    with provider_override(api) as calls:
        result = api.post(path + "/speech/generate", json={"lessonId": LESSON_ID})
        assert result.status_code == 200, result.text
        assert len(calls) >= len(board.scenes)
    alignment = result.json()["chapters"][0]["lessons"][0]["alignment"]
    assert alignment["status"] == "audio_aligned"
    assert alignment["settings"]["modelId"] == "eleven_v4"
    with Session(clean_mysql) as session:
        saved = MySqlCourseRepository(session).require_by_id(CourseId(COURSE_ID)).lesson(LESSON_ID)
        assert saved.storyboard == board
        assert saved.alignment.scenes[0].transcript == board.scenes[0].narration_text
        expected = json.loads(json.dumps(asdict(saved.alignment)))
    # New application, same durable files and database, no paid provider credentials.
    from fastapi.testclient import TestClient

    with TestClient(create_app(api.app.state.settings), headers=dict(api.headers)) as fresh:
        from fixtures.authenticated_client import authenticate_client

        authenticate_client(fresh)
        cached = fresh.post(path + "/speech/generate", json={"lessonId": LESSON_ID})
        assert cached.status_code == 200 and cached.json() == result.json()
        lesson_path = path + f"/lessons/{LESSON_ID}"
        assert fresh.get(lesson_path).json()["alignment"] == alignment
        assert fresh.get(lesson_path + "/speech/alignment").json() == expected
        transcript = fresh.get(lesson_path + "/speech/transcript")
        assert transcript.status_code == 200
        assert transcript.text == "\n\n".join(s.narration_text for s in board.scenes)
        audio = fresh.get(
            lesson_path + "/speech/audio", params={"scene_id": board.scenes[0].scene_id}
        )
        assert audio.status_code == 200 and audio.content.startswith(b"RIFF")
        assert audio.headers["cache-control"] == "private, no-store"
        assert (
            fresh.get(lesson_path + "/speech/audio", params={"scene_id": "missing"}).status_code
            == 404
        )
        fresh.headers.pop("Authorization")
        fresh.cookies.clear()
        assert fresh.get(lesson_path + "/speech/transcript").status_code == 401


def test_missing_credentials_does_not_publish_audio(api, clean_mysql):
    seed(clean_mysql)
    path = f"/api/v1/courses/{COURSE_ID}"
    result = api.post(path + "/speech/generate", json={"lessonId": LESSON_ID})
    assert result.status_code == 503, result.text
    assert api.get(path + f"/lessons/{LESSON_ID}").json()["alignment"] is None


def test_bad_alignment_does_not_publish_audio(api, clean_mysql):
    seed(clean_mysql)
    path = f"/api/v1/courses/{COURSE_ID}"
    with provider_override(api, invalid="timing"):
        result = api.post(path + "/speech/generate", json={"lessonId": LESSON_ID})
    assert result.status_code == 503, result.text
    assert api.get(path + f"/lessons/{LESSON_ID}").json()["alignment"] is None


@pytest.mark.parametrize(
    "body", [{}, {"lessonId": " "}, {"lessonId": 1}, {"lessonId": LESSON_ID, "modelId": "other"}]
)
def test_transport_validation(api, body, clean_mysql):
    seed(clean_mysql)
    result = api.post(f"/api/v1/courses/{COURSE_ID}/speech/generate", json=body)
    assert result.status_code == 422


def test_fractional_measured_offsets_survive_database_cache(api, clean_mysql):
    seed(clean_mysql, scene_count=3)
    path = f"/api/v1/courses/{COURSE_ID}"
    with provider_override(api, chunk_durations=[20, 18.96, 30, 29.84, 20, 24.88]):
        generated = api.post(path + "/speech/generate", json={"lessonId": LESSON_ID})
        assert generated.status_code == 200, generated.text
    cached = api.post(path + "/speech/generate", json={"lessonId": LESSON_ID})
    assert cached.status_code == 200, cached.text
    assert cached.json() == generated.json()
    alignment = cached.json()["chapters"][0]["lessons"][0]["alignment"]
    assert alignment["scenes"][2]["timelineStartSec"] == 98.8
    assert alignment["durationSec"] == 143.68
