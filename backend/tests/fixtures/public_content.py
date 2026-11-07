"""Finished generated content and dated public/draft records for discovery tests."""

from dataclasses import replace
from datetime import UTC, datetime

from fixtures.animation import animation_inputs

from app.courses.adapters.persistence.codec import encode
from app.courses.adapters.persistence.models import CourseRecord
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord, encode_standalone
from app.courses.domain.animation import AnimationProject
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.courses.domain.syllabus import Lesson

OWNER = "user_00000000-0000-0000-0000-000000000001"


def finished_course():
    _, course, *_ = animation_inputs()
    lesson = course.chapters[0].lessons[0]
    project = AnimationProject(
        str(lesson.id),
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "test",
        lesson.alignment.duration_sec,
        review_status="skipped",
    )
    return replace(
        course._replace_lesson(replace(lesson, animation=project)),
        owner_id=OWNER,
        title="Newest public course",
    )


def seed_public_content(session):
    course = finished_course()
    generated = replace(course.chapters[0].lessons[0], title="Newest public lesson")
    old_lesson = Lesson(
        LessonId("lesson_00000000-0000-0000-0000-000000000099"),
        "Older public lesson",
        ("Motion",),
        3,
        video_url="/test-video.mp4",
    )
    draft = replace(
        old_lesson,
        id=LessonId("lesson_00000000-0000-0000-0000-000000000098"),
        title="Unfinished hidden lesson",
        video_url=None,
    )
    for day, lesson in [(1, old_lesson), (2, generated), (3, draft)]:
        standalone = StandaloneLesson(
            LessonOwnerId(OWNER), "Private creator notes", lesson, approved=lesson.plan is not None
        )
        session.add(
            StandaloneLessonRecord(
                id=str(lesson.id),
                owner_id=OWNER,
                minutes=lesson.minutes,
                created_at=datetime(2026, 1, day, tzinfo=UTC),
                payload=encode_standalone(standalone),
            )
        )
    older = replace(
        course,
        id=CourseId("course_00000000-0000-0000-0000-000000000099"),
        title="Older public course",
    )
    draft_course = replace(
        course,
        id=CourseId("course_00000000-0000-0000-0000-000000000098"),
        title="Unfinished hidden course",
        chapters=(),
        status="draft",
    )
    for day, item in [(1, older), (2, course), (3, draft_course)]:
        session.add(
            CourseRecord(
                id=str(item.id),
                title=item.title,
                status=item.status,
                payload=encode(item),
                created_at=datetime(2026, 1, day, tzinfo=UTC),
            )
        )
    session.commit()
    return course, generated, draft
