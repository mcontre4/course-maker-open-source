"""Curriculum planning values and checks, independent of the agent harness."""

from dataclasses import dataclass

from app.courses.domain.duration import Duration
from app.courses.domain.errors import CourseError
from app.courses.domain.validation import text


@dataclass(frozen=True)
class PlannedLesson:
    lesson_id: str
    chapter_id: str
    title: str
    objectives: tuple[str, ...]
    concepts: tuple[str, ...]
    prerequisites: tuple[str, ...]
    examples: tuple[str, ...]
    level: str
    video_minutes: int
    practice_minutes: int
    reading_minutes: int
    review_minutes: int
    week: int
    adjacent_context: str

    def __post_init__(self) -> None:
        text(self.lesson_id, 100)
        text(self.chapter_id, 100)
        text(self.title, 200)
        text(self.level, 200)
        text(self.adjacent_context, 2000)
        for example in self.examples:
            text(example, 2000)
        if not self.objectives or not 1 <= len(self.concepts) <= 50:
            raise CourseError("Lessons need objectives and 1–50 concepts")
        for value in (*self.objectives, *self.concepts):
            text(value, 200)
        if type(self.video_minutes) is not int or not 1 <= self.video_minutes <= 60:
            raise CourseError("Video duration must be 1–60 minutes")
        for minutes in (self.practice_minutes, self.reading_minutes, self.review_minutes):
            if type(minutes) is not int or minutes < 0:
                raise CourseError("Learning time must be a nonnegative integer")
        if type(self.week) is not int or self.week < 1:
            raise CourseError("Week must be positive")

    def total_minutes(self) -> int:
        return (
            self.video_minutes + self.practice_minutes + self.reading_minutes + self.review_minutes
        )


@dataclass(frozen=True)
class PlannedChapter:
    chapter_id: str
    title: str
    summary: str
    lessons: tuple[PlannedLesson, ...]

    def __post_init__(self) -> None:
        text(self.chapter_id, 100)
        text(self.title, 200)
        if len(self.summary) > 2000 or not 1 <= len(self.lessons) <= 100:
            raise CourseError("Chapters need 1–100 lessons and a short summary")


@dataclass(frozen=True)
class CourseGuide:
    teaching_level: str
    terminology: tuple[str, ...]
    notation: tuple[str, ...]
    style: str
    assumptions: tuple[str, ...]
    ordering_rules: tuple[str, ...]
    consistency_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.teaching_level, 2000)
        text(self.style, 10000)
        if not self.terminology or not self.ordering_rules or not self.consistency_rules:
            raise CourseError(
                "Course guide needs terminology, ordering rules, and consistency rules"
            )
        for item in (
            *self.terminology,
            *self.notation,
            *self.assumptions,
            *self.ordering_rules,
            *self.consistency_rules,
        ):
            text(item, 2000)


@dataclass(frozen=True)
class TopicCoverage:
    topic: str
    lesson_ids: tuple[str, ...]
    trade_off: str

    def __post_init__(self) -> None:
        text(self.topic, 2000)
        if len(self.trade_off) > 4000:
            raise CourseError("Topic trade-offs must be concise")


@dataclass(frozen=True)
class Curriculum:
    title: str
    audience: str
    assumptions: tuple[str, ...]
    outcomes: tuple[str, ...]
    chapters: tuple[PlannedChapter, ...]
    guide: CourseGuide
    required_topic_coverage: tuple[TopicCoverage, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.title, 120)
        text(self.audience, 2000)
        if not self.outcomes or not 1 <= len(self.chapters) <= 50:
            raise CourseError("A curriculum needs outcomes and 1–50 chapters")
        for item in (*self.outcomes, *self.assumptions, *self.warnings):
            text(item, 4000)
        if not self.required_topic_coverage:
            raise CourseError("A curriculum needs a required-topic coverage report")
        chapter_ids = [chapter.chapter_id for chapter in self.chapters]
        if len(set(chapter_ids)) != len(chapter_ids):
            raise CourseError("Chapter identifiers must be unique")
        seen: set[str] = set()
        previous_week = 1
        for chapter in self.chapters:
            for lesson in chapter.lessons:
                if lesson.chapter_id != chapter.chapter_id:
                    raise CourseError("Lesson chapter_id must match its containing chapter")
                if lesson.lesson_id in seen or not set(lesson.prerequisites) <= seen:
                    raise CourseError(
                        "Lesson IDs must be unique; prerequisites must precede lessons"
                    )
                if lesson.week < previous_week:
                    raise CourseError("Lessons must be scheduled in prerequisite order")
                previous_week = lesson.week
                seen.add(lesson.lesson_id)
        for coverage in self.required_topic_coverage:
            if not set(coverage.lesson_ids) <= seen:
                raise CourseError("Topic coverage references an unknown lesson")
            if not coverage.lesson_ids and not coverage.trade_off.strip():
                raise CourseError("Uncovered requirements need an explicit trade-off")

    def validate_budget(self, duration: Duration) -> None:
        weekly: dict[int, int] = {}
        for chapter in self.chapters:
            for lesson in chapter.lessons:
                weekly[lesson.week] = weekly.get(lesson.week, 0) + lesson.total_minutes()
        if duration.mode == "weekly":
            assert duration.weeks is not None and duration.hours_per_week is not None
            if max(weekly) > duration.weeks or max(weekly.values()) > duration.hours_per_week * 60:
                raise CourseError("Curriculum exceeds the weekly learning budget")
            if set(weekly) != set(range(1, duration.weeks + 1)):
                raise CourseError(
                    "The complete curriculum must schedule lessons in every course week"
                )
        else:
            assert duration.hours is not None
            if sum(weekly.values()) > duration.hours * 60:
                raise CourseError("Curriculum exceeds the total learning budget")
