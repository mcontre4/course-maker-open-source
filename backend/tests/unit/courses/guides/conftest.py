from dataclasses import replace

import pytest
from fakes.courses import InMemoryCourses, SequenceIds
from fakes.guide import (
    FakeOutlineCodec,
    GuideUnitOfWork,
    InMemoryGuideRepository,
    RecordingGuideAgent,
)
from fakes.lesson_agent import RecordingLessonAgent
from fakes.standalone import InMemoryStandaloneLessons
from fakes.syllabus import InMemoryConversations, RecordingSyllabusAgent
from fixtures.syllabus import curriculum, make_planned_course

from app.courses.application.guide_chats import CreateGuideThread
from app.courses.application.guide_context import GuideDependencies
from app.courses.application.guide_dto import CreateGuideThreadRequest
from app.courses.application.standalone import CreateStandaloneLesson
from app.courses.application.standalone_dto import CreateStandaloneLessonRequest

OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.fixture
def guide_dependencies():
    repository, lessons = InMemoryGuideRepository(), InMemoryStandaloneLessons()
    courses, syllabuses, ids = InMemoryCourses(), InMemoryConversations(), SequenceIds()
    uow = GuideUnitOfWork(repository, lessons, courses, syllabuses)
    return GuideDependencies(
        repository,
        lessons,
        courses,
        syllabuses,
        uow,
        ids,
        RecordingGuideAgent(uow),
        RecordingLessonAgent(uow),
        RecordingSyllabusAgent(curriculum(), uow),
        FakeOutlineCodec(),
    )


@pytest.fixture
def guide_lesson(guide_dependencies):
    d = guide_dependencies
    return CreateStandaloneLesson(d.lessons, d.uow, d.ids).execute(
        CreateStandaloneLessonRequest(OWNER, "Chemical bonds", "Explain bonds", 3)
    )


@pytest.fixture
def guide_chat(guide_dependencies, guide_lesson):
    return CreateGuideThread(guide_dependencies).execute(
        CreateGuideThreadRequest(OWNER, guide_lesson.id, "lesson", "Explore ideas")
    )


@pytest.fixture
def guide_course(guide_dependencies):
    course, _ = make_planned_course()
    course = replace(course, owner_id=OWNER)
    guide_dependencies.courses.add(course)
    return course
