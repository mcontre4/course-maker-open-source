from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TeachingBeatInput:
    title: str
    purpose: str
    teaching_notes: str
    concepts: tuple[str, ...]
    seconds: int
    check_question: str
    expected_answer: str


@dataclass(frozen=True)
class WorkedExampleInput:
    problem: str
    steps: tuple[str, ...]
    result: str


@dataclass(frozen=True)
class LessonOutlineInput:
    objectives: tuple[str, ...]
    assumed_knowledge: tuple[str, ...]
    introduced_knowledge: tuple[str, ...]
    beats: tuple[TeachingBeatInput, ...]
    required_facts: tuple[str, ...]
    equations: tuple[str, ...]
    examples: tuple[WorkedExampleInput, ...]
    misconceptions: tuple[str, ...]
    scope_boundaries: tuple[str, ...]
    feasibility_status: Literal["feasible", "infeasible"] | None = None
    feasibility_explanation: str = ""
    recommended_video_minutes: int | None = None
    recommended_scope_adjustment: str = ""


@dataclass(frozen=True)
class SaveStandaloneOutlineRequest:
    lesson_id: str
    owner_id: str
    expected_revision: int
    outline: LessonOutlineInput
