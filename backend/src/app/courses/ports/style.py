from dataclasses import dataclass
from typing import Protocol

from app.courses.domain.generation import GenerationMode
from app.courses.domain.style import LessonStyle


class StyleUnavailable(Exception):
    pass


@dataclass(frozen=True)
class VoiceOption:
    id: str
    name: str
    description: str = ""
    preview_url: str | None = None
    labels: tuple[str, ...] = ()


class VoiceCatalog(Protocol):
    def list(self) -> tuple[VoiceOption, ...]: ...


class StylePlanner(Protocol):
    def resolve(
        self,
        context: str,
        request: str,
        audience: str,
        voices: tuple[VoiceOption, ...],
        mode: GenerationMode,
        *,
        accent: str = "American",
        tone: str = "",
        pacing: str = "",
    ) -> LessonStyle: ...
