from types import SimpleNamespace

import pytest
from fakes.courses import RecordingUnitOfWork, SequenceIds
from fakes.lesson_interactive import (
    InMemoryInteractiveLessons,
    InMemoryLessonInteractives,
    InteractiveClock,
    RecordingInteractiveAgent,
    RecordingInteractiveJobs,
)
from fakes.lesson_quiz import RecordingQuizTracking

from app.courses.application.lesson_interactive import BuildLessonInteractive
from app.courses.application.lesson_interactive_dto import BuildInteractiveRequest
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_interactive import InteractiveLesson
from app.courses.domain.syllabus import Lesson

LESSON_ID = "lesson_00000000-0000-0000-0000-000000000010"
OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.fixture
def interactive_dependencies():
    lesson = InteractiveLesson(
        Lesson(LessonId(LESSON_ID), "Gravity", ("Gravity",), 1),
        OWNER,
        "Explore gravity with a pendulum",
        "Beginning physics students",
    )
    lessons, items = InMemoryInteractiveLessons(lesson), InMemoryLessonInteractives()
    uow = RecordingUnitOfWork(items)
    clock, ids, jobs = InteractiveClock(), SequenceIds(), RecordingInteractiveJobs()
    agent, tracking = RecordingInteractiveAgent(uow), RecordingQuizTracking()
    args = (lessons, items, uow, clock, ids)

    def service(cls):
        return cls(*args, jobs)

    def build(job=None):
        job = job or jobs.jobs[-1]
        return BuildLessonInteractive(*args, agent, tracking).execute(
            BuildInteractiveRequest(job.lesson_id, job.interactive_id, job.token)
        )

    return SimpleNamespace(
        lesson=lesson,
        lessons=lessons,
        items=items,
        uow=uow,
        clock=clock,
        ids=ids,
        jobs=jobs,
        agent=agent,
        tracking=tracking,
        service=service,
        build=build,
        lesson_id=LESSON_ID,
        owner=OWNER,
    )
