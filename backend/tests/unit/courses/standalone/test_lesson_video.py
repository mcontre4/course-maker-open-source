from dataclasses import replace

import pytest
from fakes.lesson_video import RecordingLessonVideo
from fixtures.animation import animation_inputs

from app.courses.application.lesson_video import (
    GetStandaloneLessonVideo,
    GetStandaloneLessonVideoRequest,
)
from app.courses.domain.animation import AnimationProject
from app.courses.domain.errors import ContentNotReady, CourseNotFound
from app.courses.domain.identifiers import LessonId

OWNER = "user_00000000-0000-0000-0000-000000000001"


def test_saved_source_is_played_outside_transaction_without_changing_lesson(standalone):
    repo, uow, _, _, created = standalone
    before = repo.require_by_id(LessonId(created.id))
    _, course, _, _ = animation_inputs()
    content = course.chapters[0].lessons[0]
    project = AnimationProject(
        str(content.id),
        "a" * 64,
        "a" * 64 + "/remotion",
        "b" * 64,
        "test",
        content.alignment.duration_sec,
    )
    before = replace(before, approved=True, content=replace(content, animation=project))
    repo.save(before)
    videos = RecordingLessonVideo(uow)
    commits = uow.commits
    result = GetStandaloneLessonVideo(repo, videos, uow).execute(
        GetStandaloneLessonVideoRequest(str(content.id), OWNER)
    )
    assert result.content == b"saved-video"
    assert videos.animations == [project]
    assert repo.require_by_id(content.id) == before
    assert uow.commits == commits


def test_another_owner_cannot_render_or_read_a_lesson(standalone):
    repo, uow, _, _, created = standalone
    videos = RecordingLessonVideo(uow)
    with pytest.raises(CourseNotFound):
        GetStandaloneLessonVideo(repo, videos, uow).execute(
            GetStandaloneLessonVideoRequest(created.id, "user_00000000-0000-0000-0000-000000000002")
        )
    assert videos.animations == []


def test_unfinished_lesson_never_calls_renderer(standalone):
    repo, uow, _, _, created = standalone
    videos = RecordingLessonVideo(uow)
    with pytest.raises(ContentNotReady):
        GetStandaloneLessonVideo(repo, videos, uow).execute(
            GetStandaloneLessonVideoRequest(created.id, OWNER)
        )
    assert videos.animations == []
