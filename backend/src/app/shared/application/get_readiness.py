from dataclasses import dataclass

from app.shared.domain.readiness import ReadinessProbe


@dataclass(frozen=True)
class ReadinessRequest:
    pass


@dataclass(frozen=True)
class ReadinessResponse:
    database: bool
    cache: bool
    storage_configured: bool


class GetReadiness:
    def __init__(self, probe: ReadinessProbe) -> None:
        self._probe = probe

    def execute(self, request: ReadinessRequest) -> ReadinessResponse:
        status = self._probe.status()
        return ReadinessResponse(status.database, status.cache, status.storage_configured)
