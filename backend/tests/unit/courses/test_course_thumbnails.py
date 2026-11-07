from dataclasses import replace

import pytest
from fakes.thumbnails import RecordingThumbnails

from app.courses.application.course_management import CreateCourse
from app.courses.application.dto import DurationRequest
from app.courses.application.requests import CreateCourseRequest
from app.courses.application.thumbnails import GenerateCourseThumbnail, ThumbnailRequest
from app.courses.domain.errors import CourseConflict
from app.courses.domain.identifiers import CourseId
from app.courses.domain.style import LessonStyle
from app.courses.domain.visual_style import VisualStyle


def test_course_and_lesson_thumbnails_are_persisted_independently(dependencies, ready):
    repository, uow, _ = dependencies
    generator = RecordingThumbnails(uow)
    service = GenerateCourseThumbnail(repository, uow, generator)
    before = repository.require_by_id(CourseId(ready.id))
    lesson = before.chapters[0].lessons[0]
    result = service.execute(ThumbnailRequest(ready.id, regenerate=True))
    assert result.image == "generated-thumbnail"
    assert repository.require_by_id(before.id).chapters == before.chapters
    result = service.execute(ThumbnailRequest(ready.id, lesson_id=str(lesson.id), regenerate=True))
    saved = repository.require_by_id(before.id)
    assert saved.lesson(str(lesson.id)) == replace(lesson, image="generated-thumbnail")
    assert result.image == "generated-thumbnail"
    assert len(generator.calls) == 2


@pytest.mark.parametrize("fail", [False, True])
def test_course_is_saved_before_drawing_and_survives_provider_failure(dependencies, fail):
    repository, uow, ids = dependencies

    def require_saved_course():
        assert len(repository.items) == 1
        assert uow.commits == 1

    generator = RecordingThumbnails(uow, fail=fail, during=require_saved_course)
    result = CreateCourse(repository, uow, ids, generator).execute(
        CreateCourseRequest("Geometry", "Explore shapes", DurationRequest("total", hours=1))
    )
    assert repository.require_by_id(CourseId(result.id)).image == (
        "" if fail else "generated-thumbnail"
    )


@pytest.mark.parametrize("thumbnail_finishes_first", [False, True])
def test_concurrent_thumbnail_and_outline_preserve_both_results(
    lesson_generation, thumbnail_finishes_first
):
    from app.courses.application.generate_lesson import GenerateLessonRequest

    planner, repository, agent, uow, before = lesson_generation
    lesson_id = str(before.chapters[0].lessons[0].id)
    request = ThumbnailRequest(str(before.id), lesson_id=lesson_id, regenerate=True)
    plan_request = GenerateLessonRequest(str(before.id), lesson_id)
    generator = RecordingThumbnails(uow)
    thumbnail = GenerateCourseThumbnail(repository, uow, generator)
    if thumbnail_finishes_first:
        agent.during_run = lambda: thumbnail.execute(request)
        planner.execute(plan_request)
    else:
        generator.during = lambda: planner.execute(plan_request)
        thumbnail.execute(request)
    saved = repository.require_by_id(before.id)
    assert saved.lesson(lesson_id).image == "generated-thumbnail"
    assert saved.lesson(lesson_id).plan is not None


@pytest.mark.parametrize("override", [False, True])
def test_course_lesson_thumbnail_uses_effective_video_style(dependencies, ready, override):
    repository, uow, _ = dependencies
    before = repository.require_by_id(CourseId(ready.id))
    course_style = LessonStyle(visual_style_id="tech-glow")
    lesson_style = LessonStyle(visual_style_id="watercolor-wash") if override else None
    lesson = replace(before.chapters[0].lessons[0], style=lesson_style)
    before = replace(before, style=course_style)._replace_lesson(lesson)
    repository.save(before)
    generator = RecordingThumbnails(uow)
    service = GenerateCourseThumbnail(repository, uow, generator)
    service.execute(ThumbnailRequest(ready.id, regenerate=True))
    service.execute(ThumbnailRequest(ready.id, lesson_id=str(lesson.id), regenerate=True))
    assert generator.visual_directions == [
        VisualStyle(course_style.visual_style_id).direction(),
        VisualStyle((lesson_style or course_style).visual_style_id).direction(),
    ]
    assert repository.require_by_id(before.id).lesson(str(lesson.id)).image == "generated-thumbnail"


def test_course_style_change_during_thumbnail_rejects_stale_image(dependencies, ready):
    repository, uow, _ = dependencies
    before = repository.require_by_id(CourseId(ready.id))
    lesson = before.chapters[0].lessons[0]
    updated = replace(before, style=LessonStyle(visual_style_id="whiteboard"))
    generator = RecordingThumbnails(uow, during=lambda: repository.save(updated))
    with pytest.raises(CourseConflict):
        GenerateCourseThumbnail(repository, uow, generator).execute(
            ThumbnailRequest(ready.id, lesson_id=str(lesson.id), regenerate=True)
        )
    assert repository.require_by_id(before.id) == updated
