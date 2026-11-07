import pytest
from fakes.agent_sessions import InMemoryAgentSessions, SessionUnitOfWork
from fakes.courses import SequenceIds

from app.courses.application.run_agent_session import RunAgentSession
from app.courses.ports.agent_sessions import AgentSessionContext


@pytest.fixture
def agent_sessions():
    repository = InMemoryAgentSessions()
    uow = SessionUnitOfWork(repository)
    ids = SequenceIds()
    return RunAgentSession(repository, uow, ids), repository, uow, ids


@pytest.fixture
def session_scope():
    return AgentSessionContext("user-one", "lesson-one", "job-one")
