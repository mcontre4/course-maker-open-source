from dataclasses import replace

import pytest
from fixtures.syllabus import curriculum

from app.courses.domain.curriculum import TopicCoverage
from app.courses.domain.duration import Duration
from app.courses.domain.errors import CourseError


@pytest.mark.parametrize(
    "change",
    [
        {"objectives": ()},
        {"concepts": ()},
        {"concepts": ("x",) * 51},
        {"video_minutes": 0},
        {"video_minutes": 61},
        {"video_minutes": True},
        {"practice_minutes": -1},
        {"reading_minutes": -1},
        {"review_minutes": -1},
        {"week": 0},
        {"week": True},
        {"title": " "},
        {"lesson_id": ""},
        {"level": ""},
        {"objectives": ("",)},
    ],
)
def test_invalid_lesson_values(change):
    with pytest.raises(CourseError):
        replace(curriculum().chapters[0].lessons[0], **change)


@pytest.mark.parametrize(
    "change",
    [
        {"lessons": ()},
        {"summary": "x" * 2001},
        {"title": ""},
        {"chapter_id": ""},
    ],
)
def test_invalid_chapters(change):
    with pytest.raises(CourseError):
        replace(curriculum().chapters[0], **change)


@pytest.mark.parametrize(
    "change",
    [
        {"outcomes": ()},
        {"chapters": ()},
        {"title": ""},
        {"audience": ""},
        {"required_topic_coverage": (TopicCoverage("missing", ("unknown",), ""),)},
        {"required_topic_coverage": (TopicCoverage("missing", (), ""),)},
    ],
)
def test_invalid_curriculum_values(change):
    with pytest.raises(CourseError):
        replace(curriculum(), **change)


def test_duplicate_chapters_rejected():
    plan = curriculum()
    with pytest.raises(CourseError, match="Chapter identifiers"):
        replace(plan, chapters=plan.chapters * 2)


@pytest.mark.parametrize("variation", ["duplicate", "forward", "week_order"])
def test_lesson_order_and_identifiers(variation):
    plan = curriculum()
    chapter = plan.chapters[0]
    first, second = chapter.lessons
    if variation == "duplicate":
        second = replace(second, lesson_id=first.lesson_id, prerequisites=())
    elif variation == "forward":
        first = replace(first, prerequisites=(second.lesson_id,))
    else:
        first = replace(first, week=2)
    with pytest.raises(CourseError):
        replace(plan, chapters=(replace(chapter, lessons=(first, second)),))


def test_valid_budgets_and_explicit_tradeoff():
    plan = replace(
        curriculum(), required_topic_coverage=(TopicCoverage("advanced", (), "Too short"),)
    )
    plan.validate_budget(Duration("total", hours=2))
    plan.validate_budget(Duration("weekly", weeks=1, hours_per_week=2))
    assert sum(ls.total_minutes() for ls in plan.chapters[0].lessons) == 90


@pytest.mark.parametrize(
    "duration", [Duration("total", hours=1), Duration("weekly", weeks=2, hours_per_week=1)]
)
def test_over_budget_rejected(duration):
    with pytest.raises(CourseError):
        curriculum().validate_budget(duration)


def test_week_outside_schedule_rejected():
    plan = curriculum()
    chapter = plan.chapters[0]
    plan = replace(
        plan,
        chapters=(replace(chapter, lessons=tuple(replace(ls, week=2) for ls in chapter.lessons)),),
    )
    with pytest.raises(CourseError):
        plan.validate_budget(Duration("weekly", weeks=1, hours_per_week=2))


def test_lesson_must_belong_to_its_containing_chapter():
    plan = curriculum()
    chapter = plan.chapters[0]
    first, second = chapter.lessons
    with pytest.raises(CourseError, match="containing chapter"):
        replace(
            plan, chapters=(replace(chapter, lessons=(replace(first, chapter_id="other"), second)),)
        )


def test_complete_curriculum_must_cover_each_requested_week():
    with pytest.raises(CourseError, match="every course week"):
        curriculum().validate_budget(Duration("weekly", weeks=2, hours_per_week=2))


def test_required_topic_coverage_cannot_be_an_empty_placeholder():
    with pytest.raises(CourseError, match="coverage report"):
        replace(curriculum(), required_topic_coverage=())


@pytest.mark.parametrize("field", ["terminology", "ordering_rules", "consistency_rules"])
def test_course_guide_must_be_usable_by_later_agents(field):
    with pytest.raises(CourseError, match="Course guide"):
        replace(curriculum().guide, **{field: ()})


def test_blank_curriculum_metadata_cannot_satisfy_coverage_or_guide():
    with pytest.raises(CourseError):
        TopicCoverage(" ", (), "Outside scope")
    with pytest.raises(CourseError):
        TopicCoverage("Advanced topics", (), "x" * 4001)
    with pytest.raises(CourseError):
        replace(curriculum().guide, terminology=(" ",))
    with pytest.raises(CourseError):
        replace(curriculum(), outcomes=(" ",))
    with pytest.raises(CourseError):
        replace(curriculum().chapters[0].lessons[0], examples=(" ",))
