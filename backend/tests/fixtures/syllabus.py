from dataclasses import replace

from app.courses.domain.course import Course
from app.courses.domain.curriculum import (
    CourseGuide,
    Curriculum,
    PlannedChapter,
    PlannedLesson,
    TopicCoverage,
)
from app.courses.domain.duration import Duration
from app.courses.domain.identifiers import ChapterId, CourseId, LessonId
from app.courses.domain.syllabus import Chapter, Lesson
from app.courses.ports.syllabus_agent import SyllabusCourseContext


def course_context(title="Python", duration=None):
    return SyllabusCourseContext(title, "Learn Python", duration or Duration("total", hours=2), ())


def curriculum():
    return Curriculum(
        title="Python",
        audience="Beginners",
        assumptions=("No programming knowledge",),
        outcomes=("Write a small program",),
        chapters=(
            PlannedChapter(
                "basics",
                "Basics",
                "First steps",
                (
                    PlannedLesson(
                        "variables",
                        "basics",
                        "Variables",
                        ("Assign a value",),
                        ("Names",),
                        (),
                        ("Name a score",),
                        "beginner",
                        10,
                        20,
                        10,
                        5,
                        1,
                        "Prepares functions",
                    ),
                    PlannedLesson(
                        "functions",
                        "basics",
                        "Functions",
                        ("Write a function",),
                        ("Calls",),
                        ("variables",),
                        (),
                        "beginner",
                        10,
                        20,
                        10,
                        5,
                        1,
                        "Builds on variables",
                    ),
                ),
            ),
        ),
        guide=CourseGuide(
            "beginner",
            ("variable",),
            (),
            "Plain language",
            (),
            ("Names before functions",),
            ("Use Python 3",),
        ),
        required_topic_coverage=(TopicCoverage("variables", ("variables",), ""),),
        warnings=(),
    )


COURSE_ID = "course_00000000-0000-0000-0000-000000000001"
CHAPTER_ID = "chapter_00000000-0000-0000-0000-000000000002"
LESSON_ID = "lesson_00000000-0000-0000-0000-000000000003"


def make_planned_course():
    original = curriculum()
    brief = replace(original.chapters[0].lessons[0], lesson_id=LESSON_ID, chapter_id=CHAPTER_ID)
    plan = replace(
        original,
        chapters=(replace(original.chapters[0], chapter_id=CHAPTER_ID, lessons=(brief,)),),
        required_topic_coverage=tuple(
            replace(item, lesson_ids=(LESSON_ID,)) for item in original.required_topic_coverage
        ),
    )
    lesson = Lesson(
        LessonId(LESSON_ID),
        brief.title,
        brief.concepts,
        brief.video_minutes,
        image="https://example.com/lesson.png",
        video_url="https://example.com/lesson.mp4",
    )
    course = Course(
        CourseId(COURSE_ID),
        original.title,
        "Learn Python",
        Duration("total", hours=2),
        owner_id="user_00000000-0000-0000-0000-000000000001",
        chapters=(
            Chapter(
                ChapterId(CHAPTER_ID),
                "Basics",
                "First steps",
                (lesson,),
                image="https://example.com/chapter.png",
            ),
        ),
    )
    return course, plan
