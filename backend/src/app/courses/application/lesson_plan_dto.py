from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TeachingBeatResponse:
    title: str
    purpose: str
    teaching_notes: str
    concepts: tuple[str, ...]
    seconds: int
    check_question: str
    expected_answer: str


@dataclass(frozen=True)
class WorkedExampleResponse:
    problem: str
    steps: tuple[str, ...]
    result: str


@dataclass(frozen=True)
class ResearchSourceResponse:
    title: str
    url: str


@dataclass(frozen=True)
class LessonPlanResponse:
    lesson_id: str
    objectives: tuple[str, ...]
    assumed_knowledge: tuple[str, ...]
    introduced_knowledge: tuple[str, ...]
    beats: tuple[TeachingBeatResponse, ...]
    required_facts: tuple[str, ...]
    equations: tuple[str, ...]
    examples: tuple[WorkedExampleResponse, ...]
    misconceptions: tuple[str, ...]
    scope_boundaries: tuple[str, ...]
    sources: tuple[ResearchSourceResponse, ...]
    feasibility_status: Literal["feasible", "infeasible"] | None = None
    feasibility_explanation: str = ""
    recommended_video_minutes: int | None = None
    recommended_scope_adjustment: str = ""
