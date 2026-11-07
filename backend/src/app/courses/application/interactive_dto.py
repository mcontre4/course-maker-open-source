from dataclasses import asdict, dataclass

from app.courses.domain.interactive import LessonInteractive


@dataclass(frozen=True)
class InteractiveSpecResponse:
    kind: str
    title: str
    objective: str
    explanation: str
    controls: tuple[str, ...]
    behavior: str
    prompts: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    initial_length: float
    initial_gravity: float
    initial_angle: float


@dataclass(frozen=True)
class InteractiveResponse:
    plan_hash: str
    reason: str
    spec: InteractiveSpecResponse | None
    html: str | None


def interactive_response(value: LessonInteractive | None) -> InteractiveResponse | None:
    if value is None:
        return None
    return InteractiveResponse(
        value.plan_hash,
        value.reason,
        InteractiveSpecResponse(**asdict(value.spec)) if value.spec else None,
        value.document,
    )
