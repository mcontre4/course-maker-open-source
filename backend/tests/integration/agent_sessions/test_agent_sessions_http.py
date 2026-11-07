import json
from contextlib import asynccontextmanager
from dataclasses import asdict, replace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fixtures.lesson_plan import lesson_plan
from fixtures.syllabus import make_planned_course
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from sqlalchemy.orm import Session, sessionmaker

from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
from app.courses.adapters.ai.lesson import PydanticLessonAgent, validate_plan
from app.courses.adapters.http import standalone
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.persistence.agent_sessions import SqlAlchemyAgentSessions
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.standalone import PlanStandaloneLesson
from app.courses.composition import build_agent_session_factory
from app.courses.domain.agent_session import AgentSessionId
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.courses.ports.lesson_agent import LessonAgentRequest

pytestmark = pytest.mark.integration
OWNER = "user_00000000-0000-0000-0000-000000000001"


def test_http_returns_and_resumes_a_session_after_app_restart(session_database):
    course, _ = make_planned_course()
    lesson = StandaloneLesson(LessonOwnerId(OWNER), "Teach Python", course.chapters[0].lessons[0])
    expected = replace(lesson_plan(lesson.brief()), sources=())
    with Session(session_database) as session:
        SqlAlchemyStandaloneLessons(session).add(lesson)
        session.commit()
    calls = []

    def model(messages, info):
        calls.append(list(messages))
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(asdict(expected)))]
        )

    def create_api():
        @asynccontextmanager
        async def scope():
            agent = Agent(
                FunctionModel(model), output_type=LessonPlan, deps_type=LessonAgentRequest
            )
            agent.output_validator(validate_plan)
            yield agent

        factory = build_agent_session_factory(sessionmaker(session_database))
        agent = PydanticLessonAgent(scope, "test-model", PersistentAgentSessions(factory))

        def plan_use_case():
            with Session(session_database) as session:
                yield PlanStandaloneLesson(
                    SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session), agent
                )

        def owner(request: Request):
            return request.headers.get("X-Test-Owner", OWNER)

        app = FastAPI()
        app.include_router(standalone.router)
        register_error_handlers(app)
        app.dependency_overrides[standalone.get_owner] = owner
        app.dependency_overrides[standalone.get_plan] = plan_use_case
        return app

    path = f"/api/v1/lessons/{lesson.content.id}/plan"
    with TestClient(create_api()) as client:
        first = client.post(path, json={"message": "First outline", "expectedRevision": 0})
        assert first.status_code == 200, (first.text, calls[-1])
        first = first.json()
    session_id = first["content"]["agentSessions"]["outline"]
    assert session_id.startswith("agent_")
    with TestClient(create_api()) as client:
        second = client.post(
            path,
            json={
                "message": "Add another example",
                "expectedRevision": first["revision"],
                "sessionId": session_id,
            },
        )
        assert second.status_code == 200, second.text
        second = second.json()
        assert second["content"]["agentSessions"]["outline"] == session_id
        assert sum(isinstance(p, UserPromptPart) for m in calls[-1] for p in m.parts) == 2
        denied = client.post(
            path,
            json={
                "message": "Read their context",
                "expectedRevision": second["revision"],
                "sessionId": session_id,
            },
            headers={"X-Test-Owner": "user_00000000-0000-0000-0000-000000000002"},
        )
        assert denied.status_code == 404
        assert len(calls) == 2
        independent = client.post(
            path, json={"message": "A separate approach", "expectedRevision": second["revision"]}
        )
        assert independent.status_code == 200, independent.text
        assert independent.json()["content"]["agentSessions"]["outline"] != session_id
        assert sum(isinstance(p, UserPromptPart) for m in calls[-1] for p in m.parts) == 1
    with Session(session_database) as session:
        history = SqlAlchemyAgentSessions(session).require_by_id(AgentSessionId(session_id))
        assert history.revision == 2
