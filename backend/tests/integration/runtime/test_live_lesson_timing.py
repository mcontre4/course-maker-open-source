"""Opt-in paid check of duration-first planning through HTTP and real persistence."""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from fakes.generation import GatedThumbnails
from fastapi.testclient import TestClient
from fixtures.lesson_plan import lesson_plan
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.composition import build_lesson_agent, build_storyboard_agent
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.style import LessonStyle
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("LESSON_TIMING_LIVE_ENV_FILE"), reason="Opt-in paid LLM smoke test"
    ),
]

BROAD_TOPIC = (
    "Explain quantum computing to a curious beginner. I'm interested in qubits, "
    "superposition, interference, entanglement, gates, algorithms and error correction."
)
MANDATORY_SCOPE = (
    "I require full step-by-step derivations of the quadratic formula, product rule, "
    "chain rule and integration by parts, with a worked example of each. Assume the "
    "learner only knows arithmetic. Every derivation, intermediate algebra step and "
    "worked example is mandatory; do not omit any of them."
)
SPECIFIC_OBJECTIVE = (
    "Derive the quadratic formula, product rule, chain rule and integration by parts "
    "from arithmetic, showing every intermediate algebra step and one worked example each."
)


@pytest.mark.parametrize(
    "title, description, minutes, expected_status, saved_objective",
    [
        ("Quantum computing", BROAD_TOPIC, 1, "feasible", None),
        ("Quantum computing", BROAD_TOPIC, 5, "feasible", None),
        ("Four complete derivations", MANDATORY_SCOPE, 1, "infeasible", None),
        (
            "Calculus",
            "Introduce calculus to a beginner. Choose a focus that fits the available time.",
            1,
            "infeasible",
            SPECIFIC_OBJECTIVE,
        ),
    ],
    ids=["short-topic", "long-topic", "mandatory-conflict", "specific-objective-conflict"],
)
def test_duration_first_planning_with_live_agents(
    runtime_settings,
    live_lesson_settings,
    clean_mysql,
    tmp_path,
    request,
    title,
    description,
    minutes,
    expected_status,
    saved_objective,
):
    # Only the agents under test receive paid-provider credentials. Thumbnails,
    # voice selection, quizzes and rendering stay outside this planning smoke.
    app = create_app(
        runtime_settings,
        lesson_agent=build_lesson_agent(live_lesson_settings),
        storyboard_agent=build_storyboard_agent(live_lesson_settings),
    )
    headers = {"Authorization": f"Bearer {runtime_settings.api_key.get_secret_value()}"}
    with TestClient(app, headers=headers) as author:
        created = author.post(
            "/api/v1/lessons",
            json={
                "title": title,
                "description": description,
                "minutes": minutes,
                "style": {"visualStyleId": "flat-vector-science", "audience": "Beginners"},
            },
        )
        assert created.status_code == 201, created.text
        draft = created.json()
        path = f"/api/v1/lessons/{draft['id']}"
        if saved_objective:
            # Manual edits (and course copies) can retain specific objectives
            # even when the standalone description is only a broad topic request.
            with Session(clean_mysql) as session:
                repository = SqlAlchemyStandaloneLessons(session)
                lesson = repository.require_by_id(LessonId(draft["id"]))
                initial_plan = lesson_plan(lesson.brief())
                edited = lesson.revise(
                    "Initial outline", initial_plan, PlanGeneration("test", 0, 0, 0)
                )
                repository.save(
                    edited.edit_outline(replace(initial_plan, objectives=(saved_objective,)))
                )
                session.commit()
            draft = author.get(path).json()
        planned = author.post(
            path + "/plan",
            json={"expectedRevision": draft["revision"], "message": description},
        )
        assert planned.status_code == 200, planned.text
        result = planned.json()
        plan = result["content"]["plan"]
        destination = Path(os.environ.get("LESSON_TIMING_LIVE_OUTPUT", str(tmp_path)))
        destination.mkdir(parents=True, exist_ok=True)
        name = request.node.callspec.id
        (destination / f"{name}-outline.json").write_text(json.dumps(result, indent=2))
        assert plan["feasibilityStatus"] == expected_status
        if saved_objective:
            assert plan["objectives"] == [saved_objective]
        assert result["content"]["minutes"] == minutes
        seconds = sum(beat["seconds"] for beat in plan["beats"])
        if expected_status == "feasible":
            assert seconds == minutes * 60
        else:
            assert seconds > minutes * 60
        assert author.get(path).json() == result
        approved = author.post(path + "/approve", json={"expectedRevision": result["revision"]})
        if expected_status == "infeasible":
            assert approved.status_code == 409, approved.text
            assert plan["feasibilityExplanation"]
            assert plan["recommendedVideoMinutes"] == (seconds + 59) // 60
            assert author.get(path).json() == result
        else:
            assert approved.status_code == 200, approved.text
            result = approved.json()
            assert plan["recommendedVideoMinutes"] is None
            # Exercise the handoff to real scripting for the short timeline.
            if minutes == 1:
                scripted = author.post(
                    path + "/storyboard",
                    json={"expectedRevision": approved.json()["revision"]},
                )
                assert scripted.status_code == 200, scripted.text
                result = scripted.json()
                board = result["content"]["storyboard"]
                assert board["targetVideoMinutes"] == minutes
                assert abs(sum(s["targetDurationSec"] for s in board["scenes"]) - seconds) <= 30
                assert author.get(path).json() == result
                (destination / f"{name}-script.json").write_text(json.dumps(result, indent=2))
        cookies = dict(author.cookies)
    # A fresh application without live agents restores exactly the same artifact.
    with TestClient(create_app(runtime_settings), headers=headers) as restored:
        restored.cookies.update(cookies)
        assert restored.get(path).json() == result
    print(json.dumps({"case": name, "status": expected_status, "beatSeconds": seconds}))


@pytest.mark.parametrize("style_source", ["fresh", "saved", "explicit-coverage"])
def test_one_minute_pendulum_scope_with_live_style_and_planning(
    live_lesson_settings, clean_mysql, tmp_path, style_source
):
    explicit = (
        "Require full derivations of the exact large-angle period, the small-angle formula, "
        "and the damped driven pendulum equation, with a complete worked example of each. "
        "All derivations and examples are mandatory for a beginner with no calculus."
        if style_source == "explicit-coverage"
        else ""
    )
    # Exercise production style composition and the live Fast lesson model. Only
    # the thumbnail is deterministic; no speech/animation/quiz is requested.
    app = create_app(live_lesson_settings, thumbnail_generator=GatedThumbnails())
    headers = {"Authorization": f"Bearer {live_lesson_settings.api_key.get_secret_value()}"}
    with TestClient(app, headers=headers) as author:
        response = author.post(
            "/api/v1/lessons",
            json={
                "title": "Pendulum physics",
                "description": "Pendulum physics",
                "minutes": 1,
                "generationMode": "fast",
                "style": {"visualStyleId": "whiteboard", "description": explicit},
            },
        )
        assert response.status_code == 201, response.text
        draft = response.json()
        path = f"/api/v1/lessons/{draft['id']}"
        if style_source == "saved":
            # The exact inferred teaching direction from the reported failure
            # must not become a mandatory survey when an old style is reused.
            with Session(clean_mysql) as session:
                repository = SqlAlchemyStandaloneLessons(session)
                lesson = repository.require_by_id(LessonId(draft["id"]))
                style = LessonStyle(
                    teaching=(
                        "Introduce the pendulum through an everyday example, then explain forces, "
                        "energy exchange and period. Define variables and state the small-angle "
                        "assumptions before using the period formula."
                    ),
                    visual_style_id="whiteboard",
                    resolved=True,
                )
                repository.save(replace(lesson, content=replace(lesson.content, style=style)))
                session.commit()
        response = author.post(
            path + "/plan",
            json={
                "expectedRevision": draft["revision"],
                "message": "Pendulum physics",
                "generationMode": "fast",
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        content = result["content"]
        plan = content["plan"]
        destination = Path(os.environ.get("LESSON_TIMING_LIVE_OUTPUT", str(tmp_path)))
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"pendulum-{style_source}.json").write_text(json.dumps(result, indent=2))
        assert content["style"]["resolved"]
        assert content["style"]["request"] == explicit
        assert content["minutes"] == 1
        seconds = sum(beat["seconds"] for beat in plan["beats"])
        if explicit:
            assert plan["feasibilityStatus"] == "infeasible"
            assert seconds > 60
        else:
            assert plan["feasibilityStatus"] == "feasible", plan["feasibilityExplanation"]
            assert seconds == 60
        approved = author.post(path + "/approve", json={"expectedRevision": result["revision"]})
        assert approved.status_code == (409 if explicit else 200), approved.text
        restored = author.get(path)
        assert restored.status_code == 200
        assert restored.json()["content"]["plan"] == plan
        print(json.dumps({"styleSource": style_source, "status": plan["feasibilityStatus"]}))
