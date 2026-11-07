import pytest
from fixtures.syllabus import LESSON_ID

from app.courses.application.generate_video import GenerateCourseVideo, GenerateCourseVideoRequest
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animator_model import AnimatorModel


@pytest.mark.parametrize("model", [None, *AnimatorModel])
def test_course_video_runs_saved_stages_in_fast_mode(
    lesson_generation, storyboard_generation, speech_generation, animation_generation, model
):
    outline, courses, _, _, course = lesson_generation
    video = GenerateCourseVideo(
        outline, storyboard_generation[0], speech_generation[0], animation_generation[0]
    )
    result = video.execute(
        GenerateCourseVideoRequest(str(course.id), LESSON_ID, GenerationMode.FAST, model)
    )
    assert courses.require_by_id(course.id).lesson(LESSON_ID).animation is not None
    assert result.chapters[0].lessons[0].animation is not None
    assert animation_generation[2].calls[0].generation_mode is GenerationMode.FAST

    assert animation_generation[2].calls[0].animator_model == model
