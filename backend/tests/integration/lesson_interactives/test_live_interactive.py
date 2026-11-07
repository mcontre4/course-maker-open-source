"""Opt-in paid smoke with a real provider and disposable persistence."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import httpx
import pytest
from fastapi.testclient import TestClient
from fixtures.lesson_interactive_app import (
    HEADERS,
    TEST_KEY,
    create_interactive_lesson,
    interactive_test_app,
)
from sqlalchemy.orm import Session, sessionmaker

from app.courses.adapters.ai.spend import ProviderBilling, ProviderUsageTracking
from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.composition import build_interactive_agent
from app.courses.domain.identifiers import LessonId
from app.courses.ports.animator_model import AnimatorModel
from app.shared.infrastructure.settings import Settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("LESSON_INTERACTIVE_LIVE_ENV_FILE"),
        reason="Opt-in paid interactive generation",
    ),
]


def test_live_build_refinement_publication_and_spend(interactive_database, tmp_path):
    engine = interactive_database
    config = Settings(
        _env_file=os.environ["LESSON_INTERACTIVE_LIVE_ENV_FILE"],
        database_url="mysql+pymysql://unused:unused@localhost/unused",
        api_key=TEST_KEY,
    )
    assert config.openrouter_api_key.get_secret_value(), "OpenRouter credentials are required"
    spend = SqlSpendRepository(sessionmaker(engine, expire_on_commit=False))

    def complete(client, path):
        deadline = monotonic() + 330
        while monotonic() < deadline:
            response = client.get(path)
            assert response.status_code == 200, response.text
            item = response.json()
            if item["build"] is None:
                assert item["failure"] is None, item["failure"]
                return item
            sleep(0.25)
        pytest.fail("The live interactive build did not finish")

    with httpx.Client(timeout=30) as billing_client, ThreadPoolExecutor(max_workers=2) as workers:
        tracking = ProviderUsageTracking(
            spend,
            ProviderBilling(billing_client, config.openrouter_api_key.get_secret_value(), None),
        )
        app = interactive_test_app(
            engine, build_interactive_agent(config, tracking), workers, tracking, config
        )
        with TestClient(app, headers=HEADERS) as owner:
            lesson_id = create_interactive_lesson(owner)
            root = f"/api/v1/lessons/{lesson_id}/interactives"
            response = owner.post(
                root,
                json={
                    "brief": "Make a simple pendulum lab. Learners adjust length and gravity, "
                    "see the pendulum swing, and compare its predicted period. "
                    "Use two labelled range sliders, a pause button and reset. "
                    "Keep it simple and include the units.",
                    "generationMode": "balanced",
                },
                headers={"X-Generation-Model": AnimatorModel.TERRA_FAST.value},
            )
            assert response.status_code == 201, response.text
            path = root + "/" + response.json()["id"]
            first = complete(owner, path)
            assert first["currentVersion"] == 1 and 2 <= len(first["prompts"]) <= 4
            assert len(first["html"].encode()) <= 512 * 1024
            owner.put(path + "/published", json={"version": 1})
            first = owner.get(path).json()
            changed = owner.post(
                path + "/changes",
                json={
                    "instruction": (
                        "Add a button labelled Earth that restores gravity to 9.81 m/s²."
                    ),
                    "expectedRevision": first["revision"],
                },
                headers={"X-Generation-Model": AnimatorModel.TERRA_FAST.value},
            )
            assert changed.status_code == 200, changed.text
            second = complete(owner, path)
            assert second["currentVersion"] == 2 and second["publishedVersion"] == 1
            assert second["publishedHtml"] == first["html"]
            assert second["title"] == first["title"] and second["prompts"] == first["prompts"]
            assert "Earth" in second["html"]
            with Session(engine) as session:
                lessons = SqlAlchemyStandaloneLessons(session)
                lesson = lessons.require_by_id(LessonId(lesson_id))
                lessons.save(
                    replace(
                        lesson,
                        content=replace(lesson.content, video_url="https://example.com/video.mp4"),
                    )
                )
                session.commit()
            public = owner.get(f"/api/v1/published/lessons/{lesson_id}/interactives").json()[
                "items"
            ][0]
            assert public["html"] == first["html"] and public["version"] == 1
        charges = spend.list_by_lesson_id(lesson_id)
        assert len(charges) >= 2 and all(c.stage == "interactive" for c in charges)
        assert {c.model for c in charges} == {AnimatorModel.TERRA_FAST.value}
        steps = spend.list_steps(lesson_id=lesson_id)
        assert len(steps) == 2 and all(s.finished_at is not None for s in steps)
        destination = Path(os.environ.get("LESSON_INTERACTIVE_LIVE_OUTPUT", str(tmp_path)))
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "first.html").write_text(first["html"])
        (destination / "updated.html").write_text(second["html"])
        result = {
            "lessonId": lesson_id,
            "title": first["title"],
            "models": sorted({c.model for c in charges}),
            "requests": len(charges),
            "versions": 2,
            "publishedVersion": public["version"],
        }
        (destination / "verification.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
