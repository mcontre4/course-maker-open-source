from dataclasses import replace

import pytest

from app.courses.application.run_agent_session import (
    AgentTurnResponse,
    RunAgentSession,
    RunAgentSessionRequest,
)
from app.courses.domain.agent_session import AgentSessionId
from app.courses.domain.errors import CourseConflict, CourseNotFound

pytestmark = pytest.mark.asyncio


async def test_context_is_restored_by_a_new_interactor(agent_sessions, session_scope):
    service, repository, uow, ids = agent_sessions

    async def first(session_id, history):
        assert not history and not uow.active
        return AgentTurnResponse("draft", "native-history")

    created = await service.execute(RunAgentSessionRequest(session_scope, "script", first))
    resumed_service = RunAgentSession(repository, uow, ids)

    async def second(session_id, history):
        assert session_id == created.session_id
        assert history == "native-history" and not uow.active
        return AgentTurnResponse("revision", "native-history-next")

    resumed = await resumed_service.execute(
        RunAgentSessionRequest(
            replace(session_scope, session_id=created.session_id),
            "script",
            second,
        )
    )
    assert resumed.session_id == created.session_id
    stored = repository.require_by_id(AgentSessionId(created.session_id))
    assert stored.history_json == "native-history-next" and stored.revision == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", "another-user"),
        ("resource_id", "another-lesson"),
        ("job_id", "another-job"),
    ],
)
async def test_foreign_scope_is_rejected_before_execution(
    agent_sessions,
    session_scope,
    field,
    value,
):
    service, repository, _, _ = agent_sessions

    async def first(*_):
        return AgentTurnResponse("draft", "history")

    created = await service.execute(RunAgentSessionRequest(session_scope, "script", first))
    scope = replace(session_scope, session_id=created.session_id, **{field: value})

    async def forbidden(*_):
        pytest.fail("Foreign history must never reach an agent")

    with pytest.raises(CourseNotFound):
        await service.execute(RunAgentSessionRequest(scope, "script", forbidden))
    assert repository.require_by_id(AgentSessionId(created.session_id)).revision == 1


async def test_agents_and_independent_calls_never_implicitly_share_history(
    agent_sessions,
    session_scope,
):
    service, repository, _, _ = agent_sessions

    async def run(_, history):
        assert not history
        return AgentTurnResponse("output", "history")

    first = await service.execute(RunAgentSessionRequest(session_scope, "script", run))
    second = await service.execute(RunAgentSessionRequest(session_scope, "script", run))
    third = await service.execute(RunAgentSessionRequest(session_scope, "storyboard", run))
    assert len({first.session_id, second.session_id, third.session_id}) == 3
    with pytest.raises(CourseNotFound):
        await service.execute(
            RunAgentSessionRequest(
                replace(session_scope, session_id=first.session_id),
                "storyboard",
                run,
            )
        )
    assert len(repository.items) == 3


async def test_model_failure_preserves_the_last_successful_turn(agent_sessions, session_scope):
    service, repository, _, _ = agent_sessions

    async def first(*_):
        return AgentTurnResponse("draft", "history")

    created = await service.execute(RunAgentSessionRequest(session_scope, "script", first))

    async def fail(*_):
        raise TimeoutError("model unavailable")

    with pytest.raises(TimeoutError):
        await service.execute(
            RunAgentSessionRequest(
                replace(session_scope, session_id=created.session_id),
                "script",
                fail,
            )
        )
    assert repository.require_by_id(AgentSessionId(created.session_id)).history_json == "history"


async def test_stale_turn_cannot_overwrite_a_concurrent_update(agent_sessions, session_scope):
    service, repository, _, _ = agent_sessions

    async def first(*_):
        return AgentTurnResponse("draft", "history")

    created = await service.execute(RunAgentSessionRequest(session_scope, "script", first))

    async def race(*_):
        current = repository.require_by_id(AgentSessionId(created.session_id))
        repository.save(current.advance("concurrent"), current.revision)
        return AgentTurnResponse("stale", "stale")

    with pytest.raises(CourseConflict):
        await service.execute(
            RunAgentSessionRequest(
                replace(session_scope, session_id=created.session_id),
                "script",
                race,
            )
        )
    assert repository.require_by_id(AgentSessionId(created.session_id)).history_json == "concurrent"


async def test_failed_commit_rolls_back_new_history(agent_sessions, session_scope):
    service, repository, uow, _ = agent_sessions
    uow.fail_commit = True

    async def run(*_):
        return AgentTurnResponse("draft", "history")

    with pytest.raises(RuntimeError, match="Commit failed"):
        await service.execute(RunAgentSessionRequest(session_scope, "script", run))
    assert not repository.items


@pytest.mark.parametrize("session_id", ["invalid", "agent_00000000-0000-0000-0000-000000000999"])
async def test_unknown_sessions_never_start_a_fresh_conversation(
    agent_sessions,
    session_scope,
    session_id,
):
    service, _, _, _ = agent_sessions

    async def forbidden(*_):
        pytest.fail("Unknown session must fail before execution")

    with pytest.raises(CourseNotFound):
        await service.execute(
            RunAgentSessionRequest(
                replace(session_scope, session_id=session_id),
                "script",
                forbidden,
            )
        )
