"""Opt-in paid smoke: LESSON_QUIZ_LIVE_ENV_FILE=/private/backend/.env pytest ..."""

import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from fixtures.lesson_quiz_app import create_planned_lesson, quiz_test_app
from pydantic import SecretStr
from sqlalchemy.orm import sessionmaker

from app.courses.adapters.ai.spend import ProviderBilling, ProviderUsageTracking
from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.composition import build_quiz_agent
from app.courses.ports.animator_model import AnimatorModel
from app.shared.infrastructure.settings import Settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("LESSON_QUIZ_LIVE_ENV_FILE"), reason="Opt-in paid LLM smoke test"
    ),
]


@pytest.mark.parametrize(
    "mode, model_override",
    [("fast", None), ("balanced", AnimatorModel.TERRA_FAST.value)],
    ids=["fast", "model-override"],
)
def test_fast_quiz_with_live_llm_and_persistent_grading(
    quiz_database, quiz_redis, tmp_path, mode, model_override
):
    config = Settings(
        _env_file=os.environ["LESSON_QUIZ_LIVE_ENV_FILE"],
        database_url="mysql+pymysql://unused:unused@localhost/unused",
        api_key="lesson-quiz-live-test-secret-0123456789",
    )
    assert config.openrouter_api_key.get_secret_value(), "OpenRouter credentials are required"
    spend = SqlSpendRepository(sessionmaker(quiz_database, expire_on_commit=False))
    with httpx.Client(timeout=30) as billing_client:
        billing = ProviderBilling(
            billing_client, config.openrouter_api_key.get_secret_value(), None
        )
        tracking = ProviderUsageTracking(spend, billing)
        app = quiz_test_app(
            quiz_database, quiz_redis, build_quiz_agent(config, tracking), tracking, settings=config
        )
        with TestClient(app) as author:
            lesson_id = create_planned_lesson(author, quiz_database)
            path = f"/api/v1/lessons/{lesson_id}/quiz"
            public_path = f"/api/v1/published/lessons/{lesson_id}/quiz"
            before = author.get(f"/api/v1/lessons/{lesson_id}").json()
            response = author.post(
                path + "/generate",
                json={"generationMode": mode},
                headers={"X-Generation-Model": model_override} if model_override else {},
            )
            assert response.status_code == 200, response.text
            quiz = response.json()
            assert 3 <= len(quiz["questions"]) <= 5
            assert author.get(path).json() == quiz
            assert author.get(f"/api/v1/lessons/{lesson_id}").json() == before
            with TestClient(app) as learner:
                public = learner.get(public_path).json()
                assert all(
                    "correctIndex" not in q and "explanation" not in q for q in public["questions"]
                )
                result = learner.post(
                    public_path + "/submit",
                    json={
                        "quizRevision": quiz["revision"],
                        "answers": [q["correctIndex"] for q in quiz["questions"]],
                    },
                )
                assert result.status_code == 201, result.text
                assert result.json()["passed"]
                learner_cookies = dict(learner.cookies)
            edited = author.put(
                path, json={"questions": quiz["questions"], "expectedRevision": quiz["revision"]}
            )
            assert edited.status_code == 200, edited.text
            copied = author.post(f"/api/v1/lessons/{lesson_id}/copy", json={})
            assert copied.status_code == 201, copied.text
            copy = author.get(f"/api/v1/lessons/{copied.json()['id']}/quiz").json()
            assert copy["questions"] == quiz["questions"] and copy["origin"] == "edited"
        # Fresh app has no paid providers, proving reads/grading history are persisted.
        offline_config = config.model_copy(update={"openrouter_api_key": SecretStr("")})
        with TestClient(
            quiz_test_app(quiz_database, quiz_redis, settings=offline_config)
        ) as restored:
            restored.cookies.update(learner_cookies)
            attempts = restored.get(public_path + "/attempts").json()["items"]
            assert attempts[0] == result.json()
        charges = spend.list_by_lesson_id(lesson_id)
        assert charges and all(c.stage == "quiz" for c in charges)
        if model_override:
            assert {c.model for c in charges} == {model_override}
        output = {
            "lessonId": lesson_id,
            "mode": mode,
            "questions": quiz["questions"],
            "score": result.json()["score"],
            "total": result.json()["total"],
            "models": sorted({c.model for c in charges}),
            "requests": len(charges),
            "checks": [
                "live LLM",
                "PostgreSQL persistence",
                "answer visibility",
                "server grading",
                "attempt restoration",
                "quiz replacement",
                "copy",
                "media revision",
                "spend",
            ],
        }
        destination = Path(os.environ.get("LESSON_QUIZ_LIVE_OUTPUT", str(tmp_path))) / mode
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "verification.json").write_text(json.dumps(output, indent=2))
        print(json.dumps({k: v for k, v in output.items() if k != "questions"}))
