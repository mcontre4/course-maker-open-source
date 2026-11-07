import pytest
from fakes.courses import InMemoryCourses, RecordingUnitOfWork, SequenceIds
from fakes.lesson_agent import RecordingLessonAgent
from fakes.syllabus import InMemoryConversations, RecordingSyllabusAgent, SyllabusUnitOfWork
from fixtures.syllabus import COURSE_ID, curriculum, make_planned_course

from app.courses.application import use_cases as uc
from app.courses.application.dto import (
    ChapterRequest,
    DurationRequest,
    LessonRequest,
    QuestionRequest,
)
from app.courses.application.generate_lesson import GenerateLesson
from app.courses.application.generate_syllabus import GenerateSyllabus
from app.courses.application.services import CourseServices
from app.courses.ports.syllabus_agent import SyllabusConversation


@pytest.fixture
def frozen_script():
    from fixtures.lesson_plan import lesson_plan
    from fixtures.script import script_from_board
    from fixtures.storyboard import storyboard

    _, planned = make_planned_course()
    plan = lesson_plan(planned.chapters[0].lessons[0])
    board = storyboard(plan)
    return plan, board, script_from_board(board)


@pytest.fixture
def dependencies():
    repo = InMemoryCourses()
    return repo, RecordingUnitOfWork(repo), SequenceIds()


@pytest.fixture
def draft(dependencies):
    return uc.CreateCourse(*dependencies).execute(
        uc.CreateCourseRequest("Python", "Learn Python", DurationRequest("total", hours=10))
    )


@pytest.fixture
def syllabus_request(draft):
    return uc.ReplaceSyllabusRequest(
        draft.id,
        (
            ChapterRequest(
                "Basics",
                "First steps",
                (
                    LessonRequest(
                        "Variables",
                        ("Names",),
                        10,
                        video_url="https://example.com/lesson.mp4",
                        quiz=(
                            QuestionRequest(
                                "Which is a variable?", ("x", "1"), 0, "x names a value"
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


@pytest.fixture
def outlined(dependencies, syllabus_request):
    return uc.ReplaceSyllabus(*dependencies).execute(syllabus_request)


@pytest.fixture
def ready(dependencies, outlined):
    return uc.ApproveSyllabus(*dependencies).execute(uc.CourseRequest(outlined.id))


@pytest.fixture
def services(dependencies):
    return CourseServices(
        *(
            kind(*dependencies)
            for kind in (
                uc.CreateCourse,
                uc.ListCourses,
                uc.GetCourse,
                uc.UpdateCourse,
                uc.DeleteCourse,
                uc.ReplaceSyllabus,
                uc.EditSyllabusTopic,
                uc.ApproveSyllabus,
                uc.GetLesson,
                uc.ReviewLesson,
                uc.SubmitQuiz,
                uc.GetProgress,
                uc.UpdateLessonContent,
                uc.GetQuizAttempts,
            )
        )
    )


@pytest.fixture
def generation(dependencies, draft):
    courses, _, ids = dependencies
    conversations = InMemoryConversations()
    uow = SyllabusUnitOfWork(courses, conversations)
    agent = RecordingSyllabusAgent(curriculum(), uow)
    return GenerateSyllabus(courses, conversations, agent, uow, ids), agent, conversations, uow


@pytest.fixture
def planned_course():
    return make_planned_course()


@pytest.fixture
def lesson_generation():
    draft, curriculum = make_planned_course()
    course = draft.approve()
    courses = InMemoryCourses()
    courses.add(course)
    conversations = InMemoryConversations()
    conversations.save(SyllabusConversation(COURSE_ID, 1, curriculum=curriculum), 0)
    uow = RecordingUnitOfWork(courses)
    agent = RecordingLessonAgent(uow)
    return GenerateLesson(courses, conversations, agent, uow), courses, agent, uow, course


@pytest.fixture
def storyboard_generation(lesson_generation):
    from fakes.storyboard_agent import RecordingStoryboardAgent

    from app.courses.application.generate_storyboard import GenerateStoryboard

    lesson_service, courses, _, uow, before = lesson_generation
    from app.courses.application.generate_lesson import GenerateLessonRequest

    lesson_service.execute(GenerateLessonRequest(str(before.id)))
    before = courses.require_by_id(before.id)
    conversations = InMemoryConversations()
    _, curriculum = make_planned_course()
    conversations.save(SyllabusConversation(COURSE_ID, 1, curriculum=curriculum), 0)
    agent = RecordingStoryboardAgent(uow)
    uow.commits = 0
    return (
        GenerateStoryboard(courses, conversations, agent, uow),
        courses,
        agent,
        uow,
        before,
        conversations,
    )


@pytest.fixture
def speech_generation(storyboard_generation):
    from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
    from fixtures.syllabus import LESSON_ID

    from app.courses.application.generate_speech import GenerateSpeech
    from app.courses.application.generate_storyboard import GenerateStoryboardRequest
    from app.courses.domain.speech import SpeechSettings

    storyboards, courses, _, uow, before, _ = storyboard_generation
    storyboards.execute(GenerateStoryboardRequest(str(before.id), LESSON_ID))
    before = courses.require_by_id(before.id)
    synthesizer = RecordingSpeech(uow)
    artifacts = InMemorySpeechArtifacts(uow)
    settings = SpeechSettings("test-voice")
    uow.commits = 0
    return (
        GenerateSpeech(courses, synthesizer, artifacts, settings, uow, 0.25),
        courses,
        synthesizer,
        artifacts,
        uow,
        before,
        settings,
    )


@pytest.fixture
def animation_generation(speech_generation, storyboard_generation):
    from fakes.animator import RecordingAnimator
    from fixtures.syllabus import LESSON_ID

    from app.courses.application.generate_animation import GenerateAnimation
    from app.courses.application.generate_speech import GenerateSpeechRequest

    speech, courses, _, artifacts, uow, before, _ = speech_generation
    speech.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    before = courses.require_by_id(before.id)
    conversations = storyboard_generation[5]
    animator = RecordingAnimator(uow)
    uow.commits = 0
    return (
        GenerateAnimation(courses, conversations, animator, artifacts, uow),
        courses, animator, artifacts, uow, before,
    )
