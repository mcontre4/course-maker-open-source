from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Readiness:
    database: bool
    cache: bool
    storage_configured: bool


class ReadinessProbe(Protocol):
    def status(self) -> Readiness: ...
