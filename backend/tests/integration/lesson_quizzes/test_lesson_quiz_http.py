from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pytest
from fakes.lesson_quiz import questions
from fastapi.testclient import TestClient
from fixtures.lesson_quiz_app import create_planned_lesson, quiz_test_app
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.lesson_quiz import SqlAlchemyLessonQuizzes
from app.courses.domain.identifiers import LessonId

pytestmark = pytest.mark.integration


def test_quiz_http_roundtrip_grading_ownership_and_restart(quiz_database, quiz_redis, quiz_agent):
    app = quiz_test_app(quiz_database, quiz_redis, quiz_agent)
    with TestClient(app) as author:
        lesson_id = create_planned_lesson(author, quiz_database)
        path = f"/api/v1/lessons/{lesson_id}/quiz"
        public_path = f"/api/v1/published/lessons/{lesson_id}/quiz"
        before = author.get(f"/api/v1/lessons/{lesson_id}").json()
        assert author.get(path).json() is None
        generated = author.post(path + "/generate", json={"generationMode": "fast"})
        assert generated.status_code == 200, generated.text
        saved = generated.json()
        assert saved["origin"] == "generated"
        assert saved["questions"][0]["correctIndex"] == 0
        assert author.get(path).json() == saved
        assert author.get(f"/api/v1/lessons/{lesson_id}").json() == before
        public = author.get(public_path).json()
        assert "correctIndex" not in public["questions"][0]
        assert "explanation" not in public["questions"][0]
        with TestClient(app) as learner:
            assert learner.get(path).status_code == 404
            assert learner.put(path, json={"questions": saved["questions"]}).status_code == 404
            assert learner.post(path + "/generate", json={}).status_code == 404
            assert (
                learner.post(
                    public_path + "/submit",
                    json={
                        "quizRevision": saved["revision"],
                        "answers": [0],
                        "score": 100,
                    },
                ).status_code
                == 422
            )
            for invalid in ([], [True], [-1], [9], [0, 1]):
                assert (
                    learner.post(
                        public_path + "/submit",
                        json={
                            "quizRevision": saved["revision"],
                            "answers": invalid,
                        },
                    ).status_code
                    == 422
                )
            failed = learner.post(
                public_path + "/submit",
                json={
                    "quizRevision": saved["revision"],
                    "answers": [1],
                },
            )
            assert failed.status_code == 201, failed.text
            assert failed.json()["score"] == 0
            passed = learner.post(
                public_path + "/submit",
                json={
                    "quizRevision": saved["revision"],
                    "answers": [0],
                },
            )
            assert passed.status_code == 201, passed.text
            assert passed.json()["score"] == 1 and passed.json()["passed"]
            learner_cookies = dict(learner.cookies)
            assert not author.get(public_path + "/attempts").json()["items"]
        updated = author.put(
            path, json={"questions": saved["questions"], "expectedRevision": saved["revision"]}
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["origin"] == "edited"
        assert (
            author.put(
                path, json={"questions": saved["questions"], "expectedRevision": saved["revision"]}
            ).status_code
            == 409
        )
        assert author.get(f"/api/v1/lessons/{lesson_id}").json() == before
        copy = author.post(f"/api/v1/lessons/{lesson_id}/copy", json={})
        assert copy.status_code == 201, copy.text
        copied = author.get(f"/api/v1/lessons/{copy.json()['id']}/quiz").json()
        assert copied["questions"] == saved["questions"]
        assert copied["origin"] == "edited" and copied["revision"] == 1
    reopened_app = quiz_test_app(quiz_database, quiz_redis)
    with TestClient(reopened_app) as restored:
        restored.cookies.update(learner_cookies)
        attempts = restored.get(public_path + "/attempts").json()["items"]
        assert [a["score"] for a in attempts] == [1, 0]
        assert all(a["quizRevision"] == saved["revision"] for a in attempts)
        assert (
            restored.post(
                public_path + "/submit",
                json={
                    "quizRevision": saved["revision"],
                    "answers": [0],
                },
            ).status_code
            == 409
        )
        with Session(quiz_database) as session:
            quiz = SqlAlchemyLessonQuizzes(session).get_by_lesson_id(LessonId(lesson_id))
            assert quiz.origin == "edited" and quiz.revision == 2


def test_unpublished_quiz_is_private_and_invalid_replacements_rejected(
    quiz_database, quiz_redis, quiz_agent
):
    with TestClient(quiz_test_app(quiz_database, quiz_redis, quiz_agent)) as client:
        lesson_id = create_planned_lesson(client, quiz_database, published=False)
        path = f"/api/v1/lessons/{lesson_id}/quiz"
        generated = client.post(path + "/generate", json={}).json()
        for suffix in ("", "/attempts"):
            assert (
                client.get(f"/api/v1/published/lessons/{lesson_id}/quiz{suffix}").status_code == 404
            )
        duplicate = [asdict(q) for q in questions()] * 2
        for payload in (
            {"questions": []},
            {"questions": duplicate},
            {"questions": [{**asdict(questions()[0]), "options": ["Same", "same"]}]},
        ):
            assert client.put(path, json=payload).status_code == 422
        assert client.get(path).json() == generated


def test_quiz_generation_does_not_take_the_media_operation_lock(
    quiz_database, quiz_redis, quiz_agent
):
    with TestClient(quiz_test_app(quiz_database, quiz_redis, quiz_agent)) as client:
        lesson_id = create_planned_lesson(client, quiz_database)
        quiz_redis.set(f"generation-activity:lessons:{lesson_id}", "render-token:video/generate")
        result = client.post(f"/api/v1/lessons/{lesson_id}/quiz/generate", json={})
        assert result.status_code == 200, result.text
        assert (
            quiz_redis.get(f"generation-activity:lessons:{lesson_id}")
            == "render-token:video/generate"
        )


def test_script_finishes_while_quiz_runs_and_concurrent_edits_are_preserved(
    quiz_database, quiz_redis
):
    from fakes.courses import InMemoryCourses, RecordingUnitOfWork
    from fakes.lesson_quiz import BlockingQuizAgent
    from fakes.storyboard_agent import RecordingStoryboardAgent

    probe = RecordingUnitOfWork(InMemoryCourses())
    probe.exited = True
    agent = BlockingQuizAgent()
    with ThreadPoolExecutor(max_workers=1) as workers:
        app = quiz_test_app(
            quiz_database,
            quiz_redis,
            agent,
            workers=workers,
            storyboard=RecordingStoryboardAgent(probe),
        )
        with TestClient(app) as client:
            lesson_id = create_planned_lesson(client, quiz_database)
            path = f"/api/v1/lessons/{lesson_id}"
            try:
                result = client.post(
                    path + "/script/generate",
                    json={
                        "expectedRevision": 0,
                        "generationMode": "fast",
                    },
                )
                assert result.status_code == 200, result.text
                assert agent.started.wait(timeout=2)
                assert not agent.release.is_set()
                assert result.json()["content"]["storyboard"] is not None
                saved = client.put(
                    path + "/quiz",
                    json={
                        "questions": [asdict(q) for q in questions()],
                        "expectedRevision": 0,
                    },
                )
                assert saved.status_code == 200, saved.text
                assert client.get(path).json()["revision"] == result.json()["revision"]
            finally:
                agent.release.set()
    with Session(quiz_database) as session:
        quiz = SqlAlchemyLessonQuizzes(session).get_by_lesson_id(LessonId(lesson_id))
        assert quiz.origin == "edited" and quiz.revision == 1
