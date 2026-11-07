from dataclasses import dataclass, replace

from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.validation import text
from app.shared.domain.prefixed_uuid import PrefixedUuid


class AgentSessionId(PrefixedUuid):
    prefix = "agent_"


@dataclass(frozen=True)
class AgentSession:
    id: AgentSessionId
    owner_id: str
    agent: str
    resource_id: str | None = None
    job_id: str | None = None
    history_json: str = ""
    revision: int = 0

    def __post_init__(self) -> None:
        text(self.owner_id, 100)
        text(self.agent, 50)
        for value in (self.resource_id, self.job_id):
            if value is not None:
                text(value, 100)
        if self.revision < 0:
            raise CourseConflict("Invalid agent session revision")

    def require_scope(
        self, owner_id: str, agent: str, resource_id: str | None, job_id: str | None
    ) -> None:
        if (self.owner_id, self.agent, self.resource_id) != (owner_id, agent, resource_id) or (
            job_id is not None and self.job_id != job_id
        ):
            raise CourseNotFound("Agent session not found")

    def advance(self, history_json: str) -> "AgentSession":
        if not history_json:
            raise CourseConflict("An agent session requires conversation history")
        return replace(self, history_json=history_json, revision=self.revision + 1)
