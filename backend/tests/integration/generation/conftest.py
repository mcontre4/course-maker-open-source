from dataclasses import replace

import pytest
from fakes.animator import RecordingAnimator
from fakes.courses import InMemoryCourses, RecordingUnitOfWork, SequenceIds
from fakes.lesson_agent import RecordingLessonAgent
from fakes.standalone import InMemoryStandaloneLessons
from fakes.storyboard_agent import RecordingStoryboardAgent
from fakes.syllabus import InMemoryConversations, RecordingSyllabusAgent
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fixtures.animation import animation_inputs
from fixtures.lesson_plan import lesson_plan
from fixtures.syllabus import LESSON_ID, make_planned_course
from pydantic import SecretStr

from app.courses.adapters.ai.generation import (
    RoutedAnimator,
    RoutedLessonAgent,
    RoutedStoryboardAgent,
    RoutedSyllabusAgent,
)
from app.courses.adapters.http import animation, lessons, standalone, storyboards, syllabus
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.http.router import router
from app.courses.application.generate_animation import GenerateAnimation
from app.courses.application.generate_lesson import GenerateLesson
from app.courses.application.generate_storyboard import GenerateStoryboard
from app.courses.application.generate_syllabus import GenerateSyllabus
from app.courses.application.standalone import PlanStandaloneLesson
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneStoryboard,
)
from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.syllabus_agent import SyllabusConversation
from app.shared.infrastructure.settings import Settings

OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.fixture
def profile_settings(tmp_path):
    return Settings(
        database_url="mysql+pymysql://test:test@localhost/offline",
        api_key=SecretStr("test-key-" * 4),
        openrouter_api_key=SecretStr("offline-provider-key"),
        tavily_api_key=SecretStr("offline-search-key"),
        animation_local_directory=str(tmp_path / "artifacts"),
    )


@pytest.fixture
def generation_http(request):
    stage = request.param
    model_agents = {}
    draft, curriculum = make_planned_course()
    course = draft.approve()
    if stage.endswith("storyboard"):
        plan = lesson_plan(curriculum.chapters[0].lessons[0])
        course = course.plan_lesson(LESSON_ID, plan, PlanGeneration("test", 1, 0, 1))
    artifacts = None
    if stage.endswith("animation"):
        _, course, curriculum, artifacts = animation_inputs()
    if stage == "syllabus":
        course = draft
    course = replace(course, owner_id=OWNER)
    repository = InMemoryCourses()
    repository.add(course)
    conversations = InMemoryConversations()
    conversations.items[str(course.id)] = SyllabusConversation(
        str(course.id), curriculum=curriculum
    )
    if stage.startswith("standalone-"):
        repository = InMemoryStandaloneLessons()
        content = course.lesson(LESSON_ID)
        # The shared course fixture is ten minutes; standalone invariants remain in force.
        repository.add(
            StandaloneLesson(
                LessonOwnerId(OWNER),
                "Explain this topic",
                content,
                approved=content.plan is not None,
            )
        )
    uow = RecordingUnitOfWork(repository)
    app = FastAPI()
    app.include_router(router)
    app.include_router(standalone.router)
    register_error_handlers(app)
    if stage == "syllabus":
        agents = {mode: RecordingSyllabusAgent(None, uow) for mode in GenerationMode}
        service = GenerateSyllabus(
            repository, conversations, RoutedSyllabusAgent(agents), uow, SequenceIds()
        )
        dependency = syllabus.get_generator
        path = f"/api/v1/courses/{course.id}/syllabus/generate"
        body = {"message": "Teach me", "expectedRevision": 0}
    elif stage in ("lesson", "standalone-plan"):
        agents = {mode: RecordingLessonAgent(uow) for mode in GenerationMode}
        agent = RoutedLessonAgent(agents)
        if stage == "lesson":
            service = GenerateLesson(repository, conversations, agent, uow)
            dependency = lessons.get_lesson_generator
            path = f"/api/v1/courses/{course.id}/lessons/generate"
            body = {"lessonId": LESSON_ID}
        else:
            service = PlanStandaloneLesson(repository, uow, agent)
            dependency = standalone.get_plan
            path = f"/api/v1/lessons/{LESSON_ID}/plan"
            body = {"message": "Explain this", "expectedRevision": 0}
    elif stage.endswith("storyboard"):
        agents = {mode: RecordingStoryboardAgent(uow) for mode in GenerationMode}
        agent = RoutedStoryboardAgent(agents)
        if stage == "storyboard":
            service = GenerateStoryboard(repository, conversations, agent, uow)
            dependency = storyboards.get_storyboard_generator
            path = f"/api/v1/courses/{course.id}/storyboards/generate"
            body = {"lessonId": LESSON_ID}
        else:
            service = GenerateStandaloneStoryboard(repository, uow, agent)
            dependency = standalone.get_storyboard
            path = f"/api/v1/lessons/{LESSON_ID}/storyboard"
            body = {"expectedRevision": 0}
    else:
        agents = {mode: RecordingAnimator(uow) for mode in GenerationMode}
        model_agents = {
            (mode, model): RecordingAnimator(uow)
            for mode in GenerationMode
            for model in AnimatorModel
        }
        agent = RoutedAnimator(agents, model_agents)
        if stage == "animation":
            service = GenerateAnimation(repository, conversations, agent, artifacts, uow)
            dependency = animation.get_animation_generator
            path = f"/api/v1/courses/{course.id}/animations/generate"
            body = {"lessonId": LESSON_ID, "visualStyle": "Readable diagrams"}
        else:
            service = GenerateStandaloneAnimation(repository, uow, agent, artifacts)
            dependency = standalone.get_animation
            path = f"/api/v1/lessons/{LESSON_ID}/animation"
            body = {"expectedRevision": 0}
    app.dependency_overrides[dependency] = lambda: service
    app.dependency_overrides[standalone.get_owner] = lambda: OWNER
    with TestClient(app) as client:
        yield client, path, body, agents, repository, model_agents


@pytest.fixture
def video_http(request):
    from fakes.video_generation import RecordingVideoGeneration

    from app.courses.adapters.http import video
    from app.courses.application.dto import course_response
    from app.courses.application.standalone_dto import standalone_response

    _, course, _, _ = animation_inputs()
    app = FastAPI()
    app.include_router(video.router)
    app.dependency_overrides[standalone.get_owner] = lambda: OWNER
    if request.param == "course":
        service = RecordingVideoGeneration(course_response(course))
        dependency = video.get_course_video
        path = f"/api/v1/courses/{course.id}/video/generate"
        body = {"lessonId": LESSON_ID}
    else:
        lesson = StandaloneLesson(
            LessonOwnerId(OWNER), "Explain this topic", course.lesson(LESSON_ID), approved=True
        )
        service = RecordingVideoGeneration(standalone_response(lesson))
        dependency = video.get_standalone_video
        path = f"/api/v1/lessons/{LESSON_ID}/video"
        body = {"expectedRevision": 0}
    app.dependency_overrides[dependency] = lambda: service
    with TestClient(app) as client:
        yield client, path, body, service


@pytest.fixture
def composed_generation_http(profile_settings):
    """Resolve production dependencies without executing a use case or opening a database."""
    from app.courses.composition import install_dependencies
    from app.shared.infrastructure.database import get_session

    app = FastAPI()
    app.state.settings = profile_settings
    fallback = object()
    install_dependencies(
        app,
        storage=lambda: None,
        redis=lambda: None,
        syllabus_agent=lambda: fallback,
        lesson_agent=lambda: fallback,
        storyboard_agent=lambda: fallback,
        speech=lambda: (None, None, None, 0),
        animator=lambda: fallback,
    )
    from sqlalchemy.orm import Session

    def session():
        with Session() as scoped:
            yield scoped

    app.dependency_overrides[get_session] = session
    return app, fallback


@pytest.fixture
def standalone_details_http():
    from app.courses.application.standalone import CreateStandaloneLesson, UpdateStandaloneLesson

    repository = InMemoryStandaloneLessons()
    uow = RecordingUnitOfWork(repository)
    creator = CreateStandaloneLesson(repository, uow, SequenceIds())
    updater = UpdateStandaloneLesson(repository, uow)
    app = FastAPI()
    app.include_router(standalone.router)
    register_error_handlers(app)
    app.dependency_overrides[standalone.get_owner] = lambda: OWNER
    app.dependency_overrides[standalone.get_create] = lambda: creator
    app.dependency_overrides[standalone.get_update] = lambda: updater
    with TestClient(app) as client:
        yield client, repository
