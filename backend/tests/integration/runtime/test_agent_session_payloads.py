"""Native visual-review histories exceed MySQL's default 64 MiB packet limit."""

import pytest
from pydantic_ai import Conversation, ConversationTypeAdapter
from pydantic_ai.messages import ImageUrl, ModelRequest, UserPromptPart
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.agent_sessions import SqlAlchemyAgentSessions
from app.courses.domain.agent_session import AgentSession, AgentSessionId

pytestmark = pytest.mark.integration


def test_mysql_round_trips_large_native_review_conversation(clean_mysql):
    conversation = Conversation(
        messages=[
            ModelRequest(
                parts=[UserPromptPart([ImageUrl("data:image/png;base64," + "A" * (72 * 1024**2))])]
            )
        ]
    )
    history = ConversationTypeAdapter.dump_json(conversation).decode()
    record = AgentSession(
        AgentSessionId("agent_00000000-0000-4000-8000-000000000003"),
        "packet-test-owner",
        "reviewer",
        resource_id="packet-test-lesson",
    ).advance(history)
    with Session(clean_mysql) as session:
        SqlAlchemyAgentSessions(session).add(record)
        session.commit()
    with Session(clean_mysql) as session:
        stored = SqlAlchemyAgentSessions(session).require_by_id(record.id)
    assert stored.history_json == history
    assert stored.revision == 1
