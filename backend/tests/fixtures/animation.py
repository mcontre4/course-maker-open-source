from fakes.courses import InMemoryCourses, RecordingUnitOfWork
from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fixtures.lesson_plan import lesson_plan
from fixtures.storyboard import storyboard
from fixtures.syllabus import LESSON_ID, make_planned_course

from app.courses.application.generate_speech import GenerateSpeech, GenerateSpeechRequest
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.speech import SpeechSettings
from app.courses.domain.storyboard import StoryboardGeneration
from app.courses.ports.animator import AnimationInput


def animation_inputs():
    draft, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    usage = PlanGeneration("test", 1, 0, 1)
    board = storyboard(plan)
    course = (
        draft.approve()
        .plan_lesson(LESSON_ID, plan, usage)
        .storyboard_lesson(
            LESSON_ID, board, StoryboardGeneration(usage, "a" * 64, "b" * 64, "v1", None)
        )
    )
    courses = InMemoryCourses()
    courses.add(course)
    uow = RecordingUnitOfWork(courses)
    artifacts = InMemorySpeechArtifacts(uow)
    GenerateSpeech(courses, RecordingSpeech(uow), artifacts, SpeechSettings("test"), uow).execute(
        GenerateSpeechRequest(str(course.id), LESSON_ID)
    )
    course = courses.require_by_id(course.id)
    alignment = course.lesson(LESSON_ID).alignment
    return (
        AnimationInput(
            curriculum.guide,
            plan,
            board,
            alignment,
            tuple(artifacts.read(s.audio_key) for s in alignment.scenes),
            "Readable diagrams",
        ),
        course,
        curriculum,
        artifacts,
    )
