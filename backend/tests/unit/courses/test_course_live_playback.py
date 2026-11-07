from fakes.lesson_playback import ProgressiveAnimator, RecordingLessonPlayback
from fixtures.syllabus import LESSON_ID

from app.courses.application.generate_animation import GenerateAnimation, GenerateAnimationRequest
from app.courses.application.lesson_playback import (
    GetCourseLessonPlayback,
    GetCourseLessonPlaybackRequest,
)


def test_course_source_is_saved_and_watchable_before_delivery(
    animation_generation, storyboard_generation
):
    _, courses, _, artifacts, uow, before = animation_generation
    playback = RecordingLessonPlayback(uow)
    reader = GetCourseLessonPlayback(courses, playback, uow)

    def during_delivery(project):
        assert uow.exited
        lesson = courses.require_by_id(before.id).lesson(LESSON_ID)
        assert lesson.animation == project
        assert not lesson.is_published
        courses.save(courses.require_by_id(before.id).review(LESSON_ID))
        response = reader.execute(GetCourseLessonPlaybackRequest(str(before.id), LESSON_ID))
        assert not response.video_ready
        assert response.source_hash == project.output_hash

    response = GenerateAnimation(
        courses, storyboard_generation[5], ProgressiveAnimator(during_delivery), artifacts, uow
    ).execute(GenerateAnimationRequest(str(before.id), LESSON_ID, "Saved style"))
    lesson = courses.require_by_id(before.id).lesson(LESSON_ID)
    assert lesson.animation.review_status == "skipped"
    assert lesson.is_published
    assert LESSON_ID in courses.require_by_id(before.id).reviewed
    assert uow.commits == 2
    assert response.chapters[0].lessons[0].animation.review_status == "skipped"
