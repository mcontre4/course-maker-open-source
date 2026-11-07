from dataclasses import replace

import pytest
from fixtures.syllabus import LESSON_ID

from app.courses.domain.curriculum_revision import revise_curriculum
from app.courses.domain.identifiers import LessonId


def test_unchanged_teaching_preserves_media_and_images(planned_course):
    course, plan = planned_course
    updated = revise_curriculum(course, plan, plan)
    assert updated.chapters[0].lessons[0].video_url == "https://example.com/lesson.mp4"
    assert updated.chapters[0].image == course.chapters[0].image
    assert updated.chapters[0].lessons[0].image == course.chapters[0].lessons[0].image


@pytest.mark.parametrize(
    "change",
    [
        {"concepts": ("Different topic",)},
        {"objectives": ("Teach something else",)},
        {"title": "Different lesson"},
    ],
)
def test_changed_teaching_invalidates_media_but_retains_lesson_identity(planned_course, change):
    course, plan = planned_course
    chapter = plan.chapters[0]
    revised = replace(
        plan, chapters=(replace(chapter, lessons=(replace(chapter.lessons[0], **change),)),)
    )
    lesson = revise_curriculum(course, revised, plan).chapters[0].lessons[0]
    assert lesson.id == LessonId(LESSON_ID)
    assert lesson.video_url is None and lesson.video_asset_id is None and lesson.quiz == ()


def test_guide_change_invalidates_media(planned_course):
    course, plan = planned_course
    revised = replace(plan, guide=replace(plan.guide, style="Use a different notation"))
    assert revise_curriculum(course, revised, plan).chapters[0].lessons[0].video_url is None


def test_scheduling_changes_preserve_teaching_media(planned_course):
    course, plan = planned_course
    chapter = plan.chapters[0]
    revised = replace(
        plan, chapters=(replace(chapter, lessons=(replace(chapter.lessons[0], week=2),)),)
    )
    assert revise_curriculum(course, revised, plan).chapters[0].lessons[0].video_url is not None
