"""Framework-independent views; domain objects never escape incoming use cases."""

from dataclasses import dataclass

from app.courses.domain.curriculum import Curriculum


@dataclass(frozen=True)
class PlannedLessonResponse:
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


@dataclass(frozen=True)
class PlannedChapterResponse:
    chapter_id: str
    title: str
    summary: str
    lessons: tuple[PlannedLessonResponse, ...]


@dataclass(frozen=True)
class CourseGuideResponse:
    teaching_level: str
    terminology: tuple[str, ...]
    notation: tuple[str, ...]
    style: str
    assumptions: tuple[str, ...]
    ordering_rules: tuple[str, ...]
    consistency_rules: tuple[str, ...]


@dataclass(frozen=True)
class TopicCoverageResponse:
    topic: str
    lesson_ids: tuple[str, ...]
    trade_off: str


@dataclass(frozen=True)
class CurriculumResponse:
    title: str
    audience: str
    assumptions: tuple[str, ...]
    outcomes: tuple[str, ...]
    chapters: tuple[PlannedChapterResponse, ...]
    guide: CourseGuideResponse
    required_topic_coverage: tuple[TopicCoverageResponse, ...]
    warnings: tuple[str, ...]


def curriculum_response(plan: Curriculum | None) -> CurriculumResponse | None:
    if plan is None:
        return None
    guide = plan.guide
    return CurriculumResponse(
        plan.title,
        plan.audience,
        plan.assumptions,
        plan.outcomes,
        tuple(
            PlannedChapterResponse(
                ch.chapter_id,
                ch.title,
                ch.summary,
                tuple(
                    PlannedLessonResponse(
                        ls.lesson_id,
                        ls.chapter_id,
                        ls.title,
                        ls.objectives,
                        ls.concepts,
                        ls.prerequisites,
                        ls.examples,
                        ls.level,
                        ls.video_minutes,
                        ls.practice_minutes,
                        ls.reading_minutes,
                        ls.review_minutes,
                        ls.week,
                        ls.adjacent_context,
                    )
                    for ls in ch.lessons
                ),
            )
            for ch in plan.chapters
        ),
        CourseGuideResponse(
            guide.teaching_level,
            guide.terminology,
            guide.notation,
            guide.style,
            guide.assumptions,
            guide.ordering_rules,
            guide.consistency_rules,
        ),
        tuple(
            TopicCoverageResponse(item.topic, item.lesson_ids, item.trade_off)
            for item in plan.required_topic_coverage
        ),
        plan.warnings,
    )
