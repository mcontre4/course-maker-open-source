from dataclasses import replace

import pytest

from app.courses.domain.course import Course
from app.courses.domain.duration import Duration
from app.courses.domain.errors import ContentNotReady, CourseError, CourseNotFound
from app.courses.domain.identifiers import CourseId
from app.courses.domain.quiz import Question


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "total", "hours": 0},
        {"mode": "total", "hours": float("nan")},
        {"mode": "total", "hours": 481},
        {"mode": "total", "hours": 1, "weeks": 2},
        {"mode": "weekly", "weeks": 0, "hours_per_week": 1},
        {"mode": "weekly", "weeks": 13, "hours_per_week": 1},
        {"mode": "weekly", "weeks": 1.5, "hours_per_week": 1},
        {"mode": "weekly", "weeks": 1, "hours_per_week": float("inf")},
        {"mode": "weekly", "weeks": 1, "hours_per_week": 41},
        {"mode": "unknown"},
    ],
)
def test_invalid_duration(kwargs):
    with pytest.raises(CourseError):
        Duration(**kwargs)


@pytest.mark.parametrize(
    "title,description", [(" ", "Goal"), ("x" * 121, "Goal"), ("Title", ""), ("Title", "x" * 2001)]
)
def test_invalid_details(title, description):
    with pytest.raises(CourseError):
        Course(
            CourseId("course_00000000-0000-0000-0000-000000000001"),
            title,
            description,
            Duration("total", hours=1),
        )


def test_empty_syllabus_cannot_be_approved(dependencies, draft):
    course = dependencies[0].require_by_id(CourseId(draft.id))
    with pytest.raises(ContentNotReady):
        course.approve()
    with pytest.raises(CourseNotFound):
        course.lesson("missing")


def test_duplicate_lessons_and_invalid_progress_rejected(dependencies, outlined):
    course = dependencies[0].require_by_id(CourseId(outlined.id))
    with pytest.raises(CourseError):
        replace(course, chapters=course.chapters * 2)
    with pytest.raises(CourseError):
        replace(course, completed=("missing",))
    with pytest.raises(CourseError):
        replace(course, status="unknown")


def test_video_and_quiz_can_be_deferred_but_block_learning(dependencies, outlined):
    course = dependencies[0].require_by_id(CourseId(outlined.id))
    chapter = course.chapters[0]
    lesson = replace(chapter.lessons[0], video_url=None, quiz=())
    ready = replace(course, chapters=(replace(chapter, lessons=(lesson,)),)).approve()
    with pytest.raises(ContentNotReady):
        ready.review(str(lesson.id))
    with pytest.raises(ContentNotReady):
        ready.submit(str(lesson.id), (), "attempt_1")


@pytest.mark.parametrize(
    "options,answer", [(("Only",), 0), (("a", "b"), -1), (("a", "b"), 2), (("a", ""), 0)]
)
def test_invalid_quiz(options, answer):
    with pytest.raises(CourseError):
        Question("question_1", "Prompt", options, answer, "Explanation")


@pytest.mark.parametrize(
    "mode,kwargs", [("total", {"hours": True}), ("weekly", {"weeks": 2, "hours_per_week": True})]
)
def test_duration_rejects_boolean_hours(mode, kwargs):
    with pytest.raises(CourseError):
        Duration(mode, **kwargs)


def test_lesson_rejects_ambiguous_video_sources(dependencies, outlined):
    original = dependencies[0].require_by_id(CourseId(outlined.id)).chapters[0].lessons[0]
    with pytest.raises(CourseError):
        replace(original, video_asset_id="asset_00000000-0000-0000-0000-000000000001")


def test_attempt_history_must_reference_reviewed_lessons(dependencies, ready):
    from app.courses.domain.quiz import QuizAttempt

    course = dependencies[0].require_by_id(CourseId(ready.id))
    attempt = QuizAttempt("attempt_1", str(course.chapters[0].lessons[0].id), (0,), 1, 1, True)
    with pytest.raises(CourseError):
        replace(course, attempts=(attempt,))


@pytest.mark.parametrize("score,total,passed", [(2, 1, True), (0, 1, True), (0, 0, False)])
def test_attempts_reject_inconsistent_grading(score, total, passed):
    from app.courses.domain.quiz import QuizAttempt

    with pytest.raises(CourseError):
        QuizAttempt("attempt_1", "lesson_1", (0,), score, total, passed)
