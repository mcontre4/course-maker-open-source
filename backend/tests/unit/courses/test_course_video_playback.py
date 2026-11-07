from fakes.courses import InMemoryCourses, RecordingUnitOfWork
from fakes.lesson_video import RecordingLessonVideo
from fixtures.animation import animation_inputs

from app.courses.application.lesson_video import GetCourseLessonVideo, GetCourseLessonVideoRequest
from app.courses.domain.animation import AnimationProject


def test_generated_course_video_supports_playback_and_review():
    _, course, _, _ = animation_inputs()
    lesson = course.chapters[0].lessons[0]
    project = AnimationProject(
        str(lesson.id),
        "a" * 64,
        "a" * 64 + "/remotion",
        "b" * 64,
        "test",
        lesson.alignment.duration_sec,
    )
    course = course.animate_lesson(str(lesson.id), project)
    repo = InMemoryCourses()
    repo.add(course)
    uow = RecordingUnitOfWork(repo)
    video = RecordingLessonVideo(uow)
    result = GetCourseLessonVideo(repo, video, uow).execute(
        GetCourseLessonVideoRequest(str(course.id), str(lesson.id))
    )
    assert result.content == b"saved-video"
    assert video.animations == [project]
    assert uow.commits == 0
    assert str(lesson.id) in course.review(str(lesson.id)).reviewed
