from dataclasses import replace

import pytest
from fakes.courses import RecordingUnitOfWork
from fakes.lesson_quiz import InMemoryLessonQuizzes, RecordingQuizAgent, RecordingQuizTracking
from fakes.standalone import InMemoryStandaloneLessons
from fixtures.lesson_plan import lesson_plan

from app.courses.domain.identifiers import LessonId
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.courses.domain.syllabus import Lesson

LESSON_ID = "lesson_00000000-0000-0000-0000-000000000010"
OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.fixture
def quiz_dependencies():
    lesson = StandaloneLesson(
        LessonOwnerId(OWNER),
        "Teach assignment",
        Lesson(
            LessonId(LESSON_ID),
            "Assignment",
            ("Assignment",),
            1,
            video_url="https://example.com/video.mp4",
        ),
    )
    lesson = replace(
        lesson, content=replace(lesson.content, plan=lesson_plan(lesson.brief())), approved=True
    )
    lessons, quizzes = InMemoryStandaloneLessons(), InMemoryLessonQuizzes()
    lessons.add(lesson)
    uow = RecordingUnitOfWork(quizzes)
    return lessons, quizzes, uow, RecordingQuizAgent(uow), RecordingQuizTracking()
