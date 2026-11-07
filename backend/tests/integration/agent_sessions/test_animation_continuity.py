import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fakes.canvas import CanvasCommands
from fakes.direct_animation import DirectAnimationProvider
from fixtures.animation import animation_inputs
from sqlalchemy.orm import Session

from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
from app.courses.adapters.ai.canvas_delivery import CanvasDelivery
from app.courses.adapters.ai.direct_animation import (
    DirectAnimationCall,
    DirectCanvasAnimator,
    DirectCanvasReviewer,
)
from app.courses.adapters.persistence.agent_sessions import SqlAlchemyAgentSessions
from app.courses.application.produce_canvas_animation import (
    ProduceCanvasAnimation,
    ProduceCanvasAnimationRequest,
)
from app.courses.domain.agent_session import AgentSessionId
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.animation_backend import AnimationBackend

pytestmark = pytest.mark.integration
SOURCE = (
    "window.explainer=(ctx,W,H,t)=>{FV.sky(ctx,W,H,t);};"
    "window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];"
)


def test_cached_review_creates_an_independent_session_for_another_job(
    session_database,
    persistent_sessions,
    tmp_path,
):
    inputs, _, _, _ = animation_inputs()
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    commands, provider = CanvasCommands(tools), DirectAnimationProvider()
    report = json.dumps(
        {
            "approved": True,
            "feedback": "Clear",
            "scene_checks": [
                {"scene_id": s.scene_id, "observations": "Readable"}
                for s in inputs.alignment.scenes
            ],
            "quality": dict.fromkeys(
                [
                    "style_fidelity",
                    "illustration",
                    "composition",
                    "continuity",
                    "explanation",
                    "visual_development",
                    "pacing",
                ],
                4,
            ),
        }
    )
    provider.outputs = [SOURCE, report, report]

    def clients():
        return httpx.Client(transport=httpx.MockTransport(provider))

    llm = DirectAnimationCall(
        clients,
        "test-key",
        "test-model",
        "low",
        sessions=PersistentAgentSessions(persistent_sessions),
    )
    animator = DirectCanvasAnimator(
        tmp_path, tools, "test-key", model="test-model", llm=llm, command_runner=commands
    )
    reviewer = DirectCanvasReviewer(llm)
    delivery = CanvasDelivery(tmp_path, reviewer.arguments(), reviewer.run_job, commands, "test")
    production = ProduceCanvasAnimation(animator, delivery)
    first_input = replace(
        inputs,
        animation_backend=AnimationBackend.DIRECT,
        session=AgentSessionContext("user-one", inputs.plan.lesson_id, "job-one"),
    )
    first = production.execute(ProduceCanvasAnimationRequest(first_input)).project
    second = production.execute(
        ProduceCanvasAnimationRequest(
            replace(
                first_input,
                existing_project=first,
                session=AgentSessionContext("user-one", inputs.plan.lesson_id, "job-two"),
            )
        )
    ).project
    assert len(provider.requests) == 3
    assert first.reviewer_session_id != second.reviewer_session_id
    assert second.session_id is None
    with Session(session_database) as session:
        review = SqlAlchemyAgentSessions(session).require_by_id(
            AgentSessionId(second.reviewer_session_id)
        )
        assert review.job_id == "job-two" and review.revision == 1


def test_review_repair_automatically_continues_the_original_animator_session(
    session_database,
    persistent_sessions,
    tmp_path,
):
    inputs, _, _, _ = animation_inputs()
    tools = Path(__file__).resolve().parents[4] / "tools/animator"
    commands = CanvasCommands(tools)
    provider = DirectAnimationProvider()
    provider.outputs = [
        SOURCE,
        json.dumps(
            {
                "approved": False,
                "feedback": "Enlarge labels",
                "scene_checks": [
                    {"scene_id": s.scene_id, "observations": "Enlarge labels"}
                    for s in inputs.alignment.scenes
                ],
                "quality": dict.fromkeys(
                    [
                        "style_fidelity",
                        "illustration",
                        "composition",
                        "continuity",
                        "explanation",
                        "visual_development",
                        "pacing",
                    ],
                    3,
                ),
            }
        ),
        SOURCE + "// repaired",
    ]

    def clients():
        return httpx.Client(transport=httpx.MockTransport(provider))

    llm = DirectAnimationCall(
        clients,
        "test-key",
        "test-model",
        "low",
        sessions=PersistentAgentSessions(persistent_sessions),
    )
    animator = DirectCanvasAnimator(
        tmp_path, tools, "test-key", model="test-model", llm=llm, command_runner=commands
    )
    reviewer = DirectCanvasReviewer(llm)
    delivery = CanvasDelivery(tmp_path, reviewer.arguments(), reviewer.run_job, commands, "test")
    result = ProduceCanvasAnimation(animator, delivery).execute(
        ProduceCanvasAnimationRequest(
            replace(
                inputs,
                animation_backend=AnimationBackend.DIRECT,
                session=AgentSessionContext("user-one", inputs.plan.lesson_id, "job-one"),
            )
        )
    )
    assert result.project.review_status == "repaired"
    assert result.project.session_id and result.project.reviewer_session_id
    assert result.project.session_id != result.project.reviewer_session_id
    assert len(provider.requests) == 3
    author_turns = [m for m in provider.requests[2]["messages"] if m["role"] == "assistant"]
    assert [m["content"] for m in author_turns] == [SOURCE]
    with Session(session_database) as session:
        sessions = SqlAlchemyAgentSessions(session)
        author = sessions.require_by_id(AgentSessionId(result.project.session_id))
        review = sessions.require_by_id(AgentSessionId(result.project.reviewer_session_id))
        assert (author.agent, author.revision) == ("animator", 2)
        assert (review.agent, review.revision) == ("reviewer", 1)
        assert author.owner_id == review.owner_id == "user-one"
        assert author.resource_id == review.resource_id == inputs.plan.lesson_id
