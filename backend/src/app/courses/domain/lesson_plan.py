"""The instructional-design handoff to scripting, independent of providers."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.validation import text


@dataclass(frozen=True)
class TeachingBeat:
    title: str
    purpose: str
    teaching_notes: str
    concepts: tuple[str, ...]
    seconds: int
    check_question: str
    expected_answer: str

    def __post_init__(self) -> None:
        for value in (
            self.title,
            self.purpose,
            self.teaching_notes,
            *self.concepts,
        ):
            text(value, 6000)
        if bool(self.check_question.strip()) != bool(self.expected_answer.strip()):
            raise CourseError("A diagnostic check needs both a question and an expected answer")
        for value in (self.check_question, self.expected_answer):
            if value:
                text(value, 6000)
        if not self.concepts or type(self.seconds) is not int or self.seconds <= 0:
            raise CourseError("Teaching beats need concepts and positive integer seconds")


@dataclass(frozen=True)
class WorkedExample:
    problem: str
    steps: tuple[str, ...]
    result: str

    def __post_init__(self) -> None:
        for value in (self.problem, *self.steps, self.result):
            text(value, 6000)


@dataclass(frozen=True)
class ResearchSource:
    title: str
    url: str

    def __post_init__(self) -> None:
        text(self.title, 1000)
        text(self.url, 4000)
        parsed = urlsplit(self.url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname:
            raise CourseError("Research sources must be absolute HTTP URLs")


@dataclass(frozen=True)
class LessonPlan:
    lesson_id: str
    objectives: tuple[str, ...]
    assumed_knowledge: tuple[str, ...]
    introduced_knowledge: tuple[str, ...]
    beats: tuple[TeachingBeat, ...]
    required_facts: tuple[str, ...]
    equations: tuple[str, ...]
    examples: tuple[WorkedExample, ...]
    misconceptions: tuple[str, ...]
    scope_boundaries: tuple[str, ...]
    sources: tuple[ResearchSource, ...]
    # None identifies older plans that predate an explicit feasibility assessment.
    feasibility_status: Literal["feasible", "infeasible"] | None = None
    feasibility_explanation: str = ""
    recommended_video_minutes: int | None = None
    recommended_scope_adjustment: str = ""

    def __post_init__(self) -> None:
        text(self.lesson_id, 100)
        if not self.objectives or not 1 <= len(self.beats) <= 30 or not self.examples:
            raise CourseError("Plans need objectives, 1–30 teaching beats and a primary example")
        if not self.introduced_knowledge or not self.required_facts or not self.scope_boundaries:
            raise CourseError("Plans need introduced knowledge, facts and scope boundaries")
        for value in (
            *self.objectives,
            *self.assumed_knowledge,
            *self.introduced_knowledge,
            *self.required_facts,
            *self.equations,
            *self.misconceptions,
            *self.scope_boundaries,
        ):
            text(value, 6000)
        if self.feasibility_status not in (None, "feasible", "infeasible"):
            raise CourseError("Choose a valid lesson feasibility status")
        for value in (self.feasibility_explanation, self.recommended_scope_adjustment):
            if value:
                text(value, 6000)
        if self.recommended_video_minutes is not None and (
            type(self.recommended_video_minutes) is not int
            or not 1 <= self.recommended_video_minutes <= 1440
        ):
            raise CourseError("Recommended video duration must be 1–1440 integer minutes")
        if self.feasibility_status == "infeasible":
            if not self.feasibility_explanation.strip() or self.recommended_video_minutes is None:
                raise CourseError(
                    "Infeasible plans need an explanation of insufficient time "
                    "and a positive integer duration recommendation"
                )
        elif (
            self.feasibility_explanation
            or self.recommended_video_minutes is not None
            or self.recommended_scope_adjustment
        ):
            raise CourseError("Only infeasible plans can recommend duration or scope changes")

    @property
    def minimum_video_minutes(self) -> int:
        return (sum(beat.seconds for beat in self.beats) + 59) // 60

    def require_feasible(self) -> None:
        if self.feasibility_status == "infeasible":
            recommendation = (
                f" Recommended minimum: {self.recommended_video_minutes} video minutes."
            )
            if self.recommended_scope_adjustment:
                recommendation += (
                    f" Suggested scope adjustment: {self.recommended_scope_adjustment}"
                )
            raise CourseConflict(
                f"Lesson scope needs review: {self.feasibility_explanation}{recommendation}"
            )

    def validate_brief(
        self, lesson_id: str, objectives: tuple[str, ...], concepts: tuple[str, ...], minutes: int
    ) -> None:
        if self.lesson_id != lesson_id or self.objectives != objectives:
            raise CourseError("Preserve the syllabus lesson ID and objectives exactly")
        covered = {concept for beat in self.beats for concept in beat.concepts}
        if not set(concepts) <= covered:
            raise CourseError("Every syllabus concept must appear verbatim in a teaching beat")
        total_seconds = sum(beat.seconds for beat in self.beats)
        if self.feasibility_status == "infeasible":
            if total_seconds <= minutes * 60:
                raise CourseError(
                    "Infeasible plan estimates must exceed the requested video budget"
                )
            if (
                self.recommended_video_minutes is not None
                and self.recommended_video_minutes * 60 < total_seconds
            ):
                raise CourseError(
                    "Recommended video duration must accommodate the teaching estimates"
                )
        elif self.feasibility_status == "feasible":
            if total_seconds != minutes * 60:
                raise CourseError(
                    "Teaching beat timing must total exactly the requested video budget"
                )
        # Preserve the read contract of saved plans without a feasibility assessment.
        elif abs(total_seconds - minutes * 60) > 30:
            raise CourseError("Teaching beat timing must fit the video budget within 30 seconds")


@dataclass(frozen=True)
class PlanGeneration:
    model: str
    requests: int
    tool_calls: int
    total_tokens: int
    session_id: str | None = None

    def __post_init__(self) -> None:
        text(self.model, 200)
        if any(
            type(value) is not int or value < 0
            for value in (self.requests, self.tool_calls, self.total_tokens)
        ):
            raise CourseError("Generation usage must contain nonnegative integers")
