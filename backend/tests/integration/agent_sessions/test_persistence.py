import asyncio
import importlib
import json
from contextlib import asynccontextmanager
from dataclasses import asdict, replace

import httpx
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fakes.direct_animation import DirectAnimationProvider
from fixtures.lesson_plan import lesson_plan
from fixtures.script import script_from_board, visual_output
from fixtures.storyboard import storyboard
from fixtures.syllabus import make_planned_course
from pydantic_ai import Agent, ConversationTypeAdapter
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
from app.courses.adapters.ai.direct_animation import DirectAnimationCall
from app.courses.adapters.ai.script import PydanticScriptAgent, ScriptOutput, validate_script
from app.courses.adapters.ai.scripted_storyboard import ScriptedStoryboardAgent
from app.courses.adapters.ai.storyboard import (
    PydanticStoryboardAgent,
    StoryboardOutput,
    validate_storyboard,
)
from app.courses.adapters.persistence.agent_sessions import SqlAlchemyAgentSessions
from app.courses.composition import build_agent_session_factory
from app.courses.domain.agent_session import AgentSessionId
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.script_agent import ScriptAgentRequest
from app.courses.ports.storyboard_agent import StoryboardAgentRequest, VisualStoryboardRequest

pytestmark = pytest.mark.integration
SCOPE = AgentSessionContext("user-one", "lesson-one", "job-one")


def test_explicit_resume_never_silently_falls_back_to_a_new_conversation():
    async def forbidden(_):
        pytest.fail("Resuming without persistence must not call the model")

    with pytest.raises(CourseConflict, match="persistence is not configured"):
        asyncio.run(
            PersistentAgentSessions().run(
                replace(SCOPE, session_id="agent_00000000-0000-0000-0000-000000000001"),
                "script",
                forbidden,
            )
        )


def test_native_tools_and_structured_output_survive_recreated_agents_and_engine(
    session_database,
    persistent_sessions,
):
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    expected = script_from_board(storyboard(plan))
    calls = []

    def research_fact(topic: str) -> str:
        return f"A remembered fact about {topic}"

    def model(messages, info):
        calls.append(list(messages))
        start = max(
            i for i, m in enumerate(messages) if any(isinstance(p, UserPromptPart) for p in m.parts)
        )
        if not any(
            isinstance(p, ToolReturnPart) and p.tool_name == "research_fact"
            for m in messages[start:]
            for p in m.parts
        ):
            return ModelResponse(parts=[ToolCallPart("research_fact", {"topic": "Python"})])
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(asdict(expected)))]
        )

    @asynccontextmanager
    async def scope():
        agent = Agent(
            FunctionModel(model),
            output_type=ScriptOutput,
            deps_type=ScriptAgentRequest,
            tools=[research_fact],
        )
        agent.output_validator(validate_script)
        yield agent

    request = ScriptAgentRequest(plan, curriculum.guide, 10, session=SCOPE, message="First draft")
    first = PydanticScriptAgent(scope, "test-model", PersistentAgentSessions(persistent_sessions))
    created = first.run(request)
    assert created.usage.session_id
    # A fresh pool, repository, interactor and SDK agent stand in for a server restart.
    restarted_engine = create_engine(session_database.url, pool_pre_ping=True)
    try:
        factory = build_agent_session_factory(sessionmaker(restarted_engine))
        restarted = PydanticScriptAgent(scope, "test-model", PersistentAgentSessions(factory))
        revised = restarted.run(
            replace(
                request,
                session=replace(SCOPE, session_id=created.usage.session_id),
                message="Keep my example",
            )
        )
        assert revised.script == expected
        assert revised.usage.session_id == created.usage.session_id
        assert created.usage.requests == revised.usage.requests == 2
        with Session(restarted_engine) as session:
            stored = SqlAlchemyAgentSessions(session).require_by_id(
                AgentSessionId(revised.usage.session_id)
            )
            conversation = ConversationTypeAdapter.validate_json(stored.history_json)
        assert conversation.conversation_id == created.usage.session_id
        assert stored.revision == 2
        assert (
            sum(isinstance(p, UserPromptPart) for m in conversation.messages for p in m.parts) == 2
        )
        assert (
            sum(
                isinstance(p, ToolReturnPart) and p.tool_name == "research_fact"
                for m in conversation.messages
                for p in m.parts
            )
            == 2
        )
        assert "First draft" in str(calls[2]) and "Keep my example" in str(calls[2])
    finally:
        restarted_engine.dispose()


def test_script_and_storyboard_explicitly_resume_their_own_sessions(persistent_sessions):
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    board = storyboard(plan)
    expected_script = script_from_board(board)
    script_calls, visual_calls = [], []

    def scripting(messages, info):
        script_calls.append(list(messages))
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(asdict(expected_script)))]
        )

    def visuals(messages, info):
        visual_calls.append(list(messages))
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(visual_output(board)))]
        )

    @asynccontextmanager
    async def script_scope():
        agent = Agent(
            FunctionModel(scripting), output_type=ScriptOutput, deps_type=ScriptAgentRequest
        )
        agent.output_validator(validate_script)
        yield agent

    @asynccontextmanager
    async def visual_scope():
        agent = Agent(
            FunctionModel(visuals), output_type=StoryboardOutput, deps_type=VisualStoryboardRequest
        )
        agent.output_validator(validate_storyboard)
        yield agent

    def build():
        sessions = PersistentAgentSessions(persistent_sessions)
        return ScriptedStoryboardAgent(
            PydanticScriptAgent(script_scope, "test", sessions),
            PydanticStoryboardAgent(visual_scope, "test", sessions),
        )

    request = StoryboardAgentRequest(plan, curriculum.guide, 10, session=SCOPE)
    first = build().run(request)
    assert first.usage.session_id != first.script_session_id
    second = build().run(
        replace(
            request,
            session=replace(SCOPE, session_id=first.usage.session_id),
            script_session_id=first.script_session_id,
            message="Improve the introduction",
        )
    )
    assert second.script_session_id == first.script_session_id
    assert second.usage.session_id == first.usage.session_id
    assert sum(isinstance(p, UserPromptPart) for m in script_calls[-1] for p in m.parts) == 2
    assert sum(isinstance(p, UserPromptPart) for m in visual_calls[-1] for p in m.parts) == 2
    fresh = build().run(request)
    assert fresh.script_session_id != first.script_session_id
    assert fresh.usage.session_id != first.usage.session_id
    assert sum(isinstance(p, UserPromptPart) for m in script_calls[-1] for p in m.parts) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", "user-two"),
        ("resource_id", "lesson-two"),
        ("job_id", "job-two"),
    ],
)
def test_wrong_user_lesson_or_job_never_reaches_provider(persistent_sessions, field, value):
    provider = DirectAnimationProvider()
    provider.outputs = ["draft"]

    def clients():
        return httpx.Client(transport=httpx.MockTransport(provider))

    runner = DirectAnimationCall(
        clients, "test", "test", "low", sessions=PersistentAgentSessions(persistent_sessions)
    )
    first = runner.complete_with_session("author", [], "animation", SCOPE)
    with pytest.raises(CourseNotFound):
        runner.complete_with_session(
            "author", [], "animation", replace(SCOPE, session_id=first.session_id, **{field: value})
        )
    assert len(provider.requests) == 1


def test_direct_repair_resumes_author_without_importing_reviewer_history(persistent_sessions):
    provider = DirectAnimationProvider()
    provider.outputs = ["original animation", "review findings", "repaired animation"]

    def clients():
        return httpx.Client(transport=httpx.MockTransport(provider))

    def build():
        return DirectAnimationCall(
            clients, "test", "test", "low", sessions=PersistentAgentSessions(persistent_sessions)
        )

    author = build().complete_with_session(
        "author", [{"type": "text", "text": "draft"}], "animation", SCOPE
    )
    review = build().complete_with_session(
        "review", [{"type": "text", "text": "pixels"}], "visual_review", SCOPE
    )
    repaired = build().complete_with_session(
        "repair",
        [{"type": "text", "text": "fix labels"}],
        "animation_repair",
        replace(SCOPE, session_id=author.session_id),
    )
    assert repaired.session_id == author.session_id != review.session_id
    assert any(
        m["role"] == "assistant" and m["content"] == "original animation"
        for m in provider.requests[2]["messages"]
    )
    assert "review findings" not in json.dumps(provider.requests[2]["messages"])
    with pytest.raises(CourseNotFound):
        build().complete_with_session(
            "review", [], "visual_review", replace(SCOPE, session_id=author.session_id)
        )


def test_repository_detects_lost_updates_across_connections(session_database, persistent_sessions):
    from app.courses.application.run_agent_session import AgentTurnResponse, RunAgentSessionRequest

    async def run(*_):
        return AgentTurnResponse("output", "opaque-native-json")

    with persistent_sessions() as use_case:
        result = asyncio.run(use_case.execute(RunAgentSessionRequest(SCOPE, "script", run)))
    with Session(session_database) as first, Session(session_database) as second:
        one, two = SqlAlchemyAgentSessions(first), SqlAlchemyAgentSessions(second)
        original = one.require_by_id(AgentSessionId(result.session_id))
        stale = two.require_by_id(original.id)
        first.rollback()
        second.rollback()
        one.save(original.advance("winner"), original.revision)
        first.commit()
        with pytest.raises(CourseConflict):
            two.save(stale.advance("loser"), stale.revision)
        second.rollback()
        assert two.require_by_id(original.id).history_json == "winner"


def test_migration_upgrades_and_downgrades_on_postgres(session_database):
    migration = importlib.import_module("migrations.versions.0013_agent_sessions")
    with session_database.connect() as connection:
        transaction = connection.begin()
        try:
            from app.courses.adapters.persistence.agent_sessions import AgentSessionRecord

            AgentSessionRecord.__table__.drop(connection)
            connection.execute(
                text("ALTER TABLE syllabus_conversations DROP COLUMN agent_session_id")
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert "agent_sessions" in inspect(connection).get_table_names()
                assert "agent_session_id" in {
                    c["name"] for c in inspect(connection).get_columns("syllabus_conversations")
                }
                migration.downgrade()
                assert "agent_sessions" not in inspect(connection).get_table_names()
        finally:
            transaction.rollback()
