from dataclasses import replace

from app.courses.domain.curriculum import CourseGuide
from app.courses.ports.guide import GuideRepository


def load_memory_guidance(
    repository: GuideRepository | None, owner_id: str | None, resource_id: str
) -> tuple[str, ...]:
    """Load during the caller's short read boundary, never during a model call."""
    if repository is None or owner_id is None:
        return ()
    return tuple(
        f"Remembered {'lesson decision' if m.resource_id else 'user preference'} "
        f"({m.key}): {m.content}"
        for m in repository.list_memories(owner_id, resource_id)
    )


def guide_with_memories(guide: CourseGuide, guidance: tuple[str, ...]) -> CourseGuide:
    if not guidance:
        return guide
    return replace(
        guide,
        assumptions=(
            *guide.assumptions,
            "Current settings and approved content take precedence over remembered preferences.",
            *guidance,
        ),
    )
