from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from app.courses.ports.animator import AnimationInput


@dataclass(frozen=True)
class AnimationElementSpec:
    id: str
    name: str
    description: str
    format: Literal["canvas", "svg"]
    scene_ids: tuple[str, ...]


@dataclass(frozen=True)
class PreparedAnimationElement:
    spec: AnimationElementSpec
    source: str


class AnimationElementAgent(Protocol):
    def generate(self, request: AnimationInput) -> tuple[PreparedAnimationElement, ...]: ...
