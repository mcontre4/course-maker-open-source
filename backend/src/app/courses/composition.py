from collections.abc import AsyncIterator, Callable, Iterator
from concurrent.futures import Executor
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from redis import Redis
from sqlalchemy.orm import Session

from app.courses.adapters.ai.animator import AnimationWorker
from app.courses.adapters.ai.generation import (
    RoutedAnimator,
    RoutedLessonAgent,
    RoutedQuizAgent,
    RoutedStoryboardAgent,
    RoutedSyllabusAgent,
    generation_profile,
)
from app.courses.adapters.ai.model_options import model_options
from app.courses.adapters.ai.spend import ProviderBilling, ProviderUsageTracking
from app.courses.adapters.cache.catalog import RedisCatalog
from app.courses.adapters.http.activity import RequestActivity, get_activity
from app.courses.adapters.http.animation import get_animation_generator
from app.courses.adapters.http.lesson_video import (
    get_course_playback,
    get_course_video_reader,
    get_standalone_playback,
    get_standalone_video_reader,
)
from app.courses.adapters.http.lessons import get_lesson_generator
from app.courses.adapters.http.router import get_assets, get_catalog, get_courses
from app.courses.adapters.http.speech import get_speech_generator, get_speech_reader
from app.courses.adapters.http.spend import get_spend_reader, get_spend_refresher
from app.courses.adapters.http.storyboards import get_storyboard_generator
from app.courses.adapters.http.video import (
    get_automatic_lesson,
    get_course_video,
    get_standalone_script,
    get_standalone_video,
)
from app.courses.adapters.persistence.conversations import SqlAlchemySyllabusConversations
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.adapters.video.local import LocalLessonVideo
from app.courses.adapters.video.preview import LocalLessonPlayback
from app.courses.application import use_cases as uc
from app.courses.application.assets import CreateAssetUpload, GetAssetDownload
from app.courses.application.catalog import GetCatalog
from app.courses.application.copy_lesson import CopyLesson
from app.courses.application.generate_animation import GenerateAnimation
from app.courses.application.generate_automatic import GenerateAutomaticLesson
from app.courses.application.generate_lesson import GenerateLesson
from app.courses.application.generate_speech import GenerateSpeech
from app.courses.application.generate_storyboard import GenerateStoryboard
from app.courses.application.generate_syllabus import GenerateSyllabus, GetSyllabusSession
from app.courses.application.generate_video import (
    GenerateCourseVideo,
    GenerateStandaloneScript,
    GenerateStandaloneVideo,
)
from app.courses.application.get_speech_artifact import GetSpeechArtifact
from app.courses.application.lesson_playback import (
    GetCourseLessonPlayback,
    GetStandaloneLessonPlayback,
)
from app.courses.application.lesson_video import GetCourseLessonVideo, GetStandaloneLessonVideo
from app.courses.application.run_agent_session import AgentSessionFactory, RunAgentSession
from app.courses.application.save_standalone_outline import SaveStandaloneOutline
from app.courses.application.save_standalone_script import SaveStandaloneScript
from app.courses.application.services import AssetServices, CatalogServices, CourseServices
from app.courses.application.spend import GetCourseSpend, RefreshCourseSpend
from app.courses.application.standalone_spend import GetStandaloneSpend, RefreshStandaloneSpend
from app.courses.domain.generation import GenerationMode
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator import Animator
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.guide import GuideAgent
from app.courses.ports.lesson_agent import LessonAgent
from app.courses.ports.lesson_interactive import (
    InteractiveAgent,
    InteractiveAgentRequest,
    InteractiveJob,
)
from app.courses.ports.lesson_quiz import QuizAgent, QuizAgentRequest, QuizJob, QuizJobs
from app.courses.ports.speech import SpeechArtifacts, SpeechSynthesizer
from app.courses.ports.spend import UsageTracking
from app.courses.ports.storage import Storage
from app.courses.ports.storyboard_agent import StoryboardAgent
from app.courses.ports.style import StylePlanner, VoiceCatalog, VoiceOption
from app.courses.ports.syllabus_agent import SyllabusAgent
from app.courses.ports.thumbnail_jobs import ThumbnailJob, ThumbnailJobs
from app.courses.ports.thumbnails import ThumbnailGenerator, ThumbnailUnavailable
from app.shared.infrastructure.database import get_session
from app.shared.infrastructure.settings import Settings
from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator


def build_courses(
    session: Session,
    thumbnails: ThumbnailGenerator | None = None,
    tracking: ProviderUsageTracking | None = None,
    thumbnail_jobs: ThumbnailJobs | None = None,
) -> CourseServices:
    repository = MySqlCourseRepository(session)
    uow = CourseUnitOfWork(session)
    ids = UuidIdGenerator()
    return CourseServices(
        uc.CreateCourse(repository, uow, ids, thumbnails, tracking, thumbnail_jobs),
        uc.ListCourses(repository, uow, ids),
        uc.GetCourse(repository, uow, ids),
        uc.UpdateCourse(repository, uow, ids),
        uc.DeleteCourse(repository, uow, ids),
        uc.ReplaceSyllabus(repository, uow, ids),
        uc.EditSyllabusTopic(repository, uow, ids),
        uc.ApproveSyllabus(repository, uow, ids),
        uc.GetLesson(repository, uow, ids),
        uc.ReviewLesson(repository, uow, ids),
        uc.SubmitQuiz(repository, uow, ids),
        uc.GetProgress(repository, uow, ids),
        uc.UpdateLessonContent(repository, uow, ids),
        uc.GetQuizAttempts(repository, uow, ids),
    )


def build_assets(session: Session, storage: Storage) -> AssetServices:
    repository = MySqlCourseRepository(session)
    return AssetServices(
        CreateAssetUpload(repository, storage, UuidIdGenerator(), CourseUnitOfWork(session)),
        GetAssetDownload(repository, storage, CourseUnitOfWork(session)),
    )


def build_syllabus_agent(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    session_factory: AgentSessionFactory | None = None,
    mode: GenerationMode | None = None,
    model_override: AnimatorModel | None = None,
) -> SyllabusAgent:
    if mode is None:
        return RoutedSyllabusAgent(
            {
                choice: build_syllabus_agent(
                    config,
                    tracking,
                    mode=choice,
                    model_override=model_override,
                    session_factory=session_factory,
                )
                for choice in GenerationMode
            }
        )
    profile = generation_profile(mode, model_override)
    # Optional AI dependencies are loaded only when both credentials are configured.
    from app.courses.adapters.ai.unconfigured import UnconfiguredSyllabusAgent

    if (
        not config.openrouter_api_key.get_secret_value()
        or not config.tavily_api_key.get_secret_value()
    ):
        return UnconfiguredSyllabusAgent()
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent
    from pydantic_ai.common_tools.tavily import tavily_search_tool
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider
    from tavily import AsyncTavilyClient  # type: ignore[import-untyped]

    from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
    from app.courses.adapters.ai.syllabus import (
        AgentOutput,
        ScopedSyllabusAgent,
        current_course,
        prepare_search,
        validate_curriculum,
    )

    prompt = Path(__file__).with_name("adapters").joinpath("ai/syllabus_prompt.md").read_text()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Agent[str, AgentOutput]]:
        async with AsyncExitStack() as lifecycle:
            client = await lifecycle.enter_async_context(
                AsyncOpenAI(
                    api_key=config.openrouter_api_key.get_secret_value(),
                    base_url="https://openrouter.ai/api/v1",
                    max_retries=0,
                    http_client=DefaultAsyncHttpxClient(
                        event_hooks={
                            "request": [tracking.async_request],
                            "response": [tracking.async_response],
                        }
                        if tracking
                        else {}
                    ),
                )
            )
            search_client = AsyncTavilyClient(config.tavily_api_key.get_secret_value())
            lifecycle.push_async_callback(search_client.close)
            provider = OpenRouterProvider(openai_client=client)
            model = OpenAIResponsesModel(profile.model.removesuffix(":fast"), provider=provider)
            agent = Agent(
                model,
                output_type=AgentOutput,
                deps_type=str,
                system_prompt=prompt,
                instructions=[current_course],
                tools=[
                    replace(
                        tavily_search_tool(
                            client=search_client, max_results=5, search_depth="basic"
                        ),
                        prepare=prepare_search,
                    )
                ],
                retries=2,
                tool_timeout=20,
                model_settings=OpenAIResponsesModelSettings(
                    extra_body={
                        k: v for k, v in model_options(profile.model).items() if k != "model"
                    },
                    max_tokens=16000,
                    timeout=60,
                    openai_store=False,
                    parallel_tool_calls=False,
                    openai_reasoning_effort=profile.reasoning_effort,
                ),
            )
            agent.output_validator(validate_curriculum)
            yield agent

    return ScopedSyllabusAgent(scope, PersistentAgentSessions(session_factory))


def build_syllabus_services(
    session: Session,
    agent: SyllabusAgent,
    tracking: UsageTracking | None = None,
    planner: StylePlanner | None = None,
    voices: VoiceCatalog | None = None,
) -> tuple[GenerateSyllabus, GetSyllabusSession]:
    from app.courses.adapters.persistence.guide import SqlAlchemyGuideRepository

    courses = MySqlCourseRepository(session)
    conversations = SqlAlchemySyllabusConversations(session)
    uow = CourseUnitOfWork(session)
    return (
        GenerateSyllabus(
            courses,
            conversations,
            agent,
            uow,
            UuidIdGenerator(),
            tracking,
            planner,
            voices,
            memories=SqlAlchemyGuideRepository(session),
        ),
        GetSyllabusSession(courses, conversations, uow),
    )


def install_dependencies(
    app: FastAPI,
    storage: Callable[[], Storage | None],
    redis: Callable[[], Redis],
    syllabus_agent: Callable[[], SyllabusAgent],
    lesson_agent: Callable[[], LessonAgent],
    storyboard_agent: Callable[[], StoryboardAgent],
    speech: Callable[[], tuple[SpeechSynthesizer, SpeechArtifacts, SpeechSettings, float]],
    animator: Callable[[], Animator],
    tracking: Callable[[], ProviderUsageTracking] | None = None,
    spend: Callable[[], SqlSpendRepository] | None = None,
    billing: Callable[[], ProviderBilling] | None = None,
    style_planner: Callable[[], StylePlanner | None] | None = None,
    voice_catalog: Callable[[], VoiceCatalog | None] | None = None,
    thumbnails: Callable[[], ThumbnailGenerator | None] | None = None,
    guide_agent: Callable[[], GuideAgent] | None = None,
    thumbnail_workers: Callable[[], Executor] | None = None,
    quiz_agent: Callable[[], QuizAgent] | None = None,
    quiz_workers: Callable[[], Executor] | None = None,
    interactive_agent: Callable[[], InteractiveAgent] | None = None,
    interactive_workers: Callable[[], Executor] | None = None,
    agent_sessions: Callable[[], AgentSessionFactory] | None = None,
) -> None:
    from app.courses.adapters.ai.background_interactives import BackgroundInteractiveJobs
    from app.courses.adapters.http import guide as guide_http
    from app.courses.adapters.http import lesson_interactive as interactive_http
    from app.courses.adapters.http import lesson_quiz as quiz_http
    from app.courses.adapters.http import outline as outline_http
    from app.courses.adapters.http import standalone as http
    from app.courses.adapters.http import style as style_http
    from app.courses.adapters.http import thumbnails as thumbnail_http
    from app.courses.adapters.http.lesson_owner import SignedLessonOwner
    from app.courses.adapters.http.syllabus import get_generator, get_syllabus_session
    from app.courses.adapters.persistence.guide import SqlAlchemyGuideRepository
    from app.courses.adapters.persistence.guide_codec import PydanticGuideOutlineCodec
    from app.courses.adapters.persistence.lesson_interactive import (
        SqlAlchemyInteractiveLessons,
        SqlAlchemyLessonInteractives,
    )
    from app.courses.adapters.persistence.lesson_quiz import SqlAlchemyLessonQuizzes
    from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
    from app.courses.application import guide_chats
    from app.courses.application import lesson_interactive as interactive_uc
    from app.courses.application import lesson_quiz as quiz_uc
    from app.courses.application import standalone as lessons_uc
    from app.courses.application.guide_context import GuideDependencies
    from app.courses.application.lesson_interactive_dto import BuildInteractiveRequest
    from app.courses.application.lesson_quiz_dto import GenerateLessonQuizRequest
    from app.courses.application.send_guide_message import SendGuideMessage
    from app.courses.application.standalone_media import (
        GenerateStandaloneAnimation,
        GenerateStandaloneSpeech,
        GenerateStandaloneStoryboard,
    )
    from app.courses.application.style import ListVoices, UpdateCourseStyle, UpdateStandaloneStyle
    from app.courses.application.thumbnails import (
        GenerateCourseThumbnail,
        GenerateStandaloneThumbnail,
    )
    from app.shared.infrastructure.system_clock import SystemClock

    def operation_session(
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        activity: Annotated[RequestActivity, Depends(get_activity)],
    ) -> Session:
        operation = getattr(request.state, "generation_activity", None)
        if operation:
            key, token = operation
            session.info["check_generation"] = lambda: activity.check(key, token)
        return session

    def generation_model(
        value: Annotated[AnimatorModel | None, Header(alias="X-Generation-Model")] = None,
    ) -> AnimatorModel | None:
        return value

    def selected_syllabus(model: AnimatorModel | None) -> SyllabusAgent:
        if model is None:
            return syllabus_agent()
        return build_syllabus_agent(
            app.state.settings,
            tracking() if tracking else None,
            model_override=model,
            session_factory=agent_sessions() if agent_sessions else None,
        )

    def selected_lesson(model: AnimatorModel | None) -> LessonAgent:
        if model is None:
            return lesson_agent()
        return build_lesson_agent(
            app.state.settings,
            tracking() if tracking else None,
            model_override=model,
            session_factory=agent_sessions() if agent_sessions else None,
        )

    def selected_storyboard(model: AnimatorModel | None) -> StoryboardAgent:
        if model is None:
            return storyboard_agent()
        return build_storyboard_agent(
            app.state.settings,
            tracking() if tracking else None,
            model_override=model,
            session_factory=agent_sessions() if agent_sessions else None,
        )

    def selected_style(model: AnimatorModel | None) -> StylePlanner | None:
        from app.courses.adapters.ai.style import OpenRouterStylePlanner

        planner = style_planner() if style_planner else None
        if model is not None and isinstance(planner, OpenRouterStylePlanner):
            return planner.for_model(model)
        return planner

    def guide_dependencies(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        request: Request,
        session: Annotated[Session, Depends(operation_session)],
    ) -> GuideDependencies:
        return GuideDependencies(
            SqlAlchemyGuideRepository(session),
            SqlAlchemyStandaloneLessons(session),
            MySqlCourseRepository(session),
            SqlAlchemySyllabusConversations(session),
            CourseUnitOfWork(session),
            UuidIdGenerator(),
            guide_agent()
            if guide_agent and model_override is None
            else build_guide_agent(
                request.app.state.settings,
                tracking() if tracking else None,
                model_override=model_override,
            ),
            selected_lesson(model_override),
            selected_syllabus(model_override),
            PydanticGuideOutlineCodec(),
            tracking() if tracking else None,
        )

    def create_chat(
        d: Annotated[GuideDependencies, Depends(guide_dependencies)],
    ) -> guide_chats.CreateGuideThread:
        return guide_chats.CreateGuideThread(d)

    def list_chats(
        d: Annotated[GuideDependencies, Depends(guide_dependencies)],
    ) -> guide_chats.ListGuideThreads:
        return guide_chats.ListGuideThreads(d)

    def read_chat(
        d: Annotated[GuideDependencies, Depends(guide_dependencies)],
    ) -> guide_chats.GetGuideThread:
        return guide_chats.GetGuideThread(d)

    def send_chat(d: Annotated[GuideDependencies, Depends(guide_dependencies)]) -> SendGuideMessage:
        return SendGuideMessage(d)

    def list_memories(
        d: Annotated[GuideDependencies, Depends(guide_dependencies)],
    ) -> guide_chats.ListGuideMemories:
        return guide_chats.ListGuideMemories(d)

    def change_memory(
        d: Annotated[GuideDependencies, Depends(guide_dependencies)],
    ) -> guide_chats.ChangeGuideMemory:
        return guide_chats.ChangeGuideMemory(d)

    def list_versions(
        d: Annotated[GuideDependencies, Depends(guide_dependencies)],
    ) -> guide_chats.ListOutlineVersions:
        return guide_chats.ListOutlineVersions(d)

    app.dependency_overrides.update(
        {
            guide_http.get_create_chat: create_chat,
            guide_http.get_list_chats: list_chats,
            guide_http.get_chat: read_chat,
            guide_http.get_send_message: send_chat,
            guide_http.get_memories: list_memories,
            guide_http.get_change_memory: change_memory,
            guide_http.get_versions: list_versions,
        }
    )

    def background_thumbnails(session: Session) -> ThumbnailJobs | None:
        from app.courses.adapters.ai.background_thumbnails import BackgroundThumbnailJobs
        from app.courses.application.thumbnails import ThumbnailRequest

        generator = thumbnails() if thumbnails else None
        if generator is None or thumbnail_workers is None:
            return None
        bind = session.get_bind()
        activity = RequestActivity(redis())

        def generate(job: ThumbnailJob) -> None:
            operation = f"lessons/{job.lesson_id}/thumbnail" if job.lesson_id else "thumbnail"
            kind = "courses" if job.course else "lessons"
            key = f"generation-activity:{kind}:{job.resource_id}:thumbnail"
            # Separate sessions are essential: SQLAlchemy sessions cannot cross threads.
            from fastapi import HTTPException

            try:
                token = activity.start(key, operation, lease_seconds=600)
            except HTTPException as exc:
                if exc.status_code == 409:
                    return
                raise
            try:
                with Session(bind) as scoped:
                    request = ThumbnailRequest(job.resource_id, job.owner_id, job.lesson_id)
                    if job.course:
                        GenerateCourseThumbnail(
                            MySqlCourseRepository(scoped),
                            CourseUnitOfWork(scoped),
                            generator,
                            tracking() if tracking else None,
                        ).execute(request)
                    else:
                        GenerateStandaloneThumbnail(
                            SqlAlchemyStandaloneLessons(scoped),
                            CourseUnitOfWork(scoped),
                            generator,
                            tracking() if tracking else None,
                        ).execute(request)
            finally:
                activity.finish(key, token)

        return BackgroundThumbnailJobs(thumbnail_workers(), generate)

    def selected_interactive(model: AnimatorModel | None = None) -> InteractiveAgent:
        if model is None and interactive_agent:
            return interactive_agent()
        return build_interactive_agent(
            app.state.settings,
            tracking() if tracking else None,
            model_override=model,
            session_factory=agent_sessions() if agent_sessions else None,
        )

    def interactive_services(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(get_session)],
    ) -> interactive_uc.InteractiveServices:
        bind = session.get_bind()

        def build(job: InteractiveJob) -> None:
            # Retain the engine and chosen model, never the request session.
            with Session(bind) as scoped:
                interactive_uc.BuildLessonInteractive(
                    SqlAlchemyInteractiveLessons(scoped),
                    SqlAlchemyLessonInteractives(scoped),
                    CourseUnitOfWork(scoped),
                    SystemClock(),
                    UuidIdGenerator(),
                    selected_interactive(model_override),
                    tracking() if tracking else None,
                ).execute(BuildInteractiveRequest(job.lesson_id, job.interactive_id, job.token))

        jobs = (
            BackgroundInteractiveJobs(interactive_workers(), build) if interactive_workers else None
        )
        args = (
            SqlAlchemyInteractiveLessons(session),
            SqlAlchemyLessonInteractives(session),
            CourseUnitOfWork(session),
            SystemClock(),
            UuidIdGenerator(),
            jobs,
        )
        return interactive_uc.InteractiveServices(
            interactive_uc.ListLessonInteractives(*args),
            interactive_uc.GetLessonInteractive(*args),
            interactive_uc.CreateLessonInteractive(*args),
            interactive_uc.ChangeLessonInteractive(*args),
            interactive_uc.RetryInteractiveBuild(*args),
            interactive_uc.CancelInteractiveBuild(*args),
            interactive_uc.SaveInteractiveDetails(*args),
            interactive_uc.RestoreInteractiveVersion(*args),
            interactive_uc.PublishInteractiveVersion(*args),
            interactive_uc.DeleteLessonInteractive(*args),
            interactive_uc.ReorderLessonInteractives(*args),
            interactive_uc.GetPublicLessonInteractives(*args),
        )

    app.dependency_overrides[interactive_http.get_interactives] = interactive_services

    def selected_quiz(model: AnimatorModel | None = None) -> QuizAgent:
        if model is None and quiz_agent:
            return quiz_agent()
        return build_quiz_agent(
            app.state.settings,
            tracking() if tracking else None,
            model_override=model,
            session_factory=agent_sessions() if agent_sessions else None,
        )

    def background_quizzes(session: Session, model: AnimatorModel | None) -> QuizJobs | None:
        from app.courses.adapters.ai.background_quizzes import BackgroundQuizJobs

        if quiz_workers is None:
            return None
        bind = session.get_bind()
        agent = selected_quiz(model)
        activity = RequestActivity(redis())

        def generate(job: QuizJob) -> None:
            key = f"generation-activity:lessons:{job.lesson_id}:quiz"
            try:
                token = activity.start(key, "quiz/generate", lease_seconds=600)
            except HTTPException as exc:
                if exc.status_code == 409:
                    return
                raise
            try:
                with Session(bind) as scoped:
                    quiz_uc.GenerateLessonQuiz(
                        SqlAlchemyStandaloneLessons(scoped),
                        SqlAlchemyLessonQuizzes(scoped),
                        CourseUnitOfWork(scoped),
                        agent,
                        tracking() if tracking else None,
                    ).execute(
                        GenerateLessonQuizRequest(
                            job.lesson_id, job.owner_id, job.generation_mode, only_if_missing=True
                        )
                    )
            except Exception:
                activity.failed(key, token)
                raise
            finally:
                activity.finish(key, token)

        return BackgroundQuizJobs(quiz_workers(), generate)

    def read_quiz_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> quiz_uc.GetLessonQuiz:
        return quiz_uc.GetLessonQuiz(
            SqlAlchemyStandaloneLessons(session),
            SqlAlchemyLessonQuizzes(session),
            CourseUnitOfWork(session),
        )

    def save_quiz_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> quiz_uc.SaveLessonQuiz:
        return quiz_uc.SaveLessonQuiz(
            SqlAlchemyStandaloneLessons(session),
            SqlAlchemyLessonQuizzes(session),
            CourseUnitOfWork(session),
        )

    def generate_quiz_service(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(get_session)],
    ) -> quiz_uc.GenerateLessonQuiz:
        return quiz_uc.GenerateLessonQuiz(
            SqlAlchemyStandaloneLessons(session),
            SqlAlchemyLessonQuizzes(session),
            CourseUnitOfWork(session),
            selected_quiz(model_override),
            tracking() if tracking else None,
        )

    def public_quiz_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> quiz_uc.GetPublicLessonQuiz:
        return quiz_uc.GetPublicLessonQuiz(
            SqlAlchemyStandaloneLessons(session),
            SqlAlchemyLessonQuizzes(session),
            CourseUnitOfWork(session),
        )

    def submit_quiz_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> quiz_uc.SubmitLessonQuiz:
        return quiz_uc.SubmitLessonQuiz(
            SqlAlchemyStandaloneLessons(session),
            SqlAlchemyLessonQuizzes(session),
            CourseUnitOfWork(session),
            UuidIdGenerator(),
            SystemClock(),
        )

    def quiz_attempts_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> quiz_uc.ListLessonQuizAttempts:
        return quiz_uc.ListLessonQuizAttempts(
            SqlAlchemyStandaloneLessons(session),
            SqlAlchemyLessonQuizzes(session),
            CourseUnitOfWork(session),
        )

    app.dependency_overrides.update(
        {
            quiz_http.get_quiz: read_quiz_service,
            quiz_http.save_quiz: save_quiz_service,
            quiz_http.generate_quiz: generate_quiz_service,
            quiz_http.get_public_quiz: public_quiz_service,
            quiz_http.submit_quiz: submit_quiz_service,
            quiz_http.list_attempts: quiz_attempts_service,
        }
    )

    def thumbnail_generator() -> ThumbnailGenerator:
        generator = thumbnails() if thumbnails else None
        if generator is None:
            raise ThumbnailUnavailable("Configure OpenRouter to generate thumbnails")
        return generator

    def course_thumbnail_service(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateCourseThumbnail:
        return GenerateCourseThumbnail(
            MySqlCourseRepository(session),
            CourseUnitOfWork(session),
            thumbnail_generator(),
            tracking() if tracking else None,
        )

    def lesson_thumbnail_service(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStandaloneThumbnail:
        return GenerateStandaloneThumbnail(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            thumbnail_generator(),
            tracking() if tracking else None,
        )

    app.dependency_overrides.update(
        {
            thumbnail_http.get_course_thumbnail: course_thumbnail_service,
            thumbnail_http.get_lesson_thumbnail: lesson_thumbnail_service,
        }
    )

    def voices_service() -> ListVoices:
        catalog = voice_catalog() if voice_catalog else None
        if catalog is None:
            raise HTTPException(503, "Voice catalog is unavailable")
        return ListVoices(catalog)

    def course_style_service(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> UpdateCourseStyle:
        return UpdateCourseStyle(
            MySqlCourseRepository(session),
            CourseUnitOfWork(session),
            selected_style(model_override),
            voice_catalog() if voice_catalog else None,
            tracking() if tracking else None,
        )

    def lesson_style_service(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> UpdateStandaloneStyle:
        return UpdateStandaloneStyle(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            selected_style(model_override),
            voice_catalog() if voice_catalog else None,
            tracking() if tracking else None,
        )

    app.dependency_overrides.update(
        {
            style_http.get_voices: voices_service,
            style_http.get_course_style: course_style_service,
            style_http.get_lesson_style: lesson_style_service,
        }
    )

    def standalone_video_service(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GetStandaloneLessonVideo:
        config = app.state.settings
        return GetStandaloneLessonVideo(
            SqlAlchemyStandaloneLessons(session),
            LocalLessonVideo(Path(config.animation_local_directory), config.lesson_video_image),
            CourseUnitOfWork(session),
        )

    def course_video_service(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GetCourseLessonVideo:
        config = app.state.settings
        return GetCourseLessonVideo(
            MySqlCourseRepository(session),
            LocalLessonVideo(Path(config.animation_local_directory), config.lesson_video_image),
            CourseUnitOfWork(session),
        )

    def standalone_playback_service(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GetStandaloneLessonPlayback:
        config = app.state.settings
        root = Path(config.animation_local_directory)
        return GetStandaloneLessonPlayback(
            SqlAlchemyStandaloneLessons(session),
            LocalLessonPlayback(root, LocalLessonVideo(root, config.lesson_video_image)),
            CourseUnitOfWork(session),
        )

    def course_playback_service(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GetCourseLessonPlayback:
        config = app.state.settings
        root = Path(config.animation_local_directory)
        return GetCourseLessonPlayback(
            MySqlCourseRepository(session),
            LocalLessonPlayback(root, LocalLessonVideo(root, config.lesson_video_image)),
            CourseUnitOfWork(session),
        )

    app.dependency_overrides[get_standalone_playback] = standalone_playback_service
    app.dependency_overrides[get_course_playback] = course_playback_service
    app.dependency_overrides[get_standalone_video_reader] = standalone_video_service
    app.dependency_overrides[get_course_video_reader] = course_video_service

    def owner(request: Request, response: Response) -> str:
        identity = SignedLessonOwner(
            request.app.state.settings.api_key.get_secret_value().encode(), UuidIdGenerator()
        )
        return identity.resolve(request, response)

    from app.courses.adapters.http import creators as creators_http
    from app.courses.adapters.http import learning_activity as learning_activity_http
    from app.courses.adapters.persistence.creators import SqlAlchemyCreators
    from app.courses.adapters.persistence.learning_activity import SqlAlchemyLearningActivities
    from app.courses.application import creators as creators_uc
    from app.courses.application.learning_activity import (
        GetLearningActivity,
        RecordLearningActivity,
    )

    def own_creator(
        session: Annotated[Session, Depends(operation_session)],
    ) -> creators_uc.GetOwnCreator:
        return creators_uc.GetOwnCreator(SqlAlchemyCreators(session), CourseUnitOfWork(session))

    def save_creator(
        session: Annotated[Session, Depends(operation_session)],
    ) -> creators_uc.SaveCreator:
        return creators_uc.SaveCreator(SqlAlchemyCreators(session), CourseUnitOfWork(session))

    def creator_page(
        session: Annotated[Session, Depends(operation_session)],
    ) -> creators_uc.GetCreatorPage:
        return creators_uc.GetCreatorPage(SqlAlchemyCreators(session))

    def published_lesson(
        session: Annotated[Session, Depends(operation_session)],
    ) -> creators_uc.GetPublishedLesson:
        return creators_uc.GetPublishedLesson(
            SqlAlchemyCreators(session),
            MySqlCourseRepository(session),
            storage(),
            CourseUnitOfWork(session),
        )

    def discovery(
        session: Annotated[Session, Depends(operation_session)],
    ) -> creators_uc.GetDiscovery:
        return creators_uc.GetDiscovery(SqlAlchemyCreators(session))

    def public_animation(
        session: Annotated[Session, Depends(operation_session)],
    ) -> creators_uc.GetPublishedAnimation:
        config = app.state.settings
        return creators_uc.GetPublishedAnimation(
            SqlAlchemyCreators(session),
            MySqlCourseRepository(session),
            LocalLessonVideo(Path(config.animation_local_directory), config.lesson_video_image),
            CourseUnitOfWork(session),
        )

    def learning_activity(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GetLearningActivity:
        return GetLearningActivity(SqlAlchemyLearningActivities(session))

    def record_learning_activity(
        session: Annotated[Session, Depends(operation_session)],
    ) -> RecordLearningActivity:
        return RecordLearningActivity(
            SqlAlchemyLearningActivities(session), SystemClock(), CourseUnitOfWork(session)
        )

    app.dependency_overrides[learning_activity_http.get_learning_activity] = learning_activity
    app.dependency_overrides[learning_activity_http.get_record_learning_activity] = (
        record_learning_activity
    )
    app.dependency_overrides[creators_http.get_discovery] = discovery
    app.dependency_overrides[creators_http.get_published_animation] = public_animation
    app.dependency_overrides[creators_http.get_own_creator] = own_creator
    app.dependency_overrides[creators_http.get_save_creator] = save_creator
    app.dependency_overrides[creators_http.get_creator_page] = creator_page
    app.dependency_overrides[creators_http.get_published_lesson] = published_lesson

    def update_lesson(
        session: Annotated[Session, Depends(operation_session)],
    ) -> lessons_uc.UpdateStandaloneLesson:
        return lessons_uc.UpdateStandaloneLesson(
            SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session)
        )

    def copy_lesson(
        session: Annotated[Session, Depends(get_session)],
    ) -> CopyLesson:
        return CopyLesson(
            SqlAlchemyStandaloneLessons(session),
            MySqlCourseRepository(session),
            CourseUnitOfWork(session),
            UuidIdGenerator(),
            quizzes=SqlAlchemyLessonQuizzes(session),
            interactives=SqlAlchemyLessonInteractives(session),
        )

    def create_lesson(
        session: Annotated[Session, Depends(operation_session)],
    ) -> lessons_uc.CreateStandaloneLesson:
        return lessons_uc.CreateStandaloneLesson(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            UuidIdGenerator(),
        )

    def list_lessons(
        session: Annotated[Session, Depends(operation_session)],
    ) -> lessons_uc.ListStandaloneLessons:
        return lessons_uc.ListStandaloneLessons(
            SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session)
        )

    def read_lesson(
        session: Annotated[Session, Depends(operation_session)],
    ) -> lessons_uc.GetStandaloneLesson:
        return lessons_uc.GetStandaloneLesson(
            SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session)
        )

    def plan_lesson(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> lessons_uc.PlanStandaloneLesson:
        return lessons_uc.PlanStandaloneLesson(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            selected_lesson(model_override),
            tracking=tracking() if tracking else None,
            style_planner=selected_style(model_override),
            voices=voice_catalog() if voice_catalog else None,
            thumbnail_jobs=background_thumbnails(session),
            memories=SqlAlchemyGuideRepository(session),
        )

    def save_outline(
        session: Annotated[Session, Depends(operation_session)],
    ) -> SaveStandaloneOutline:
        return SaveStandaloneOutline(
            SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session)
        )

    def save_script(
        session: Annotated[Session, Depends(operation_session)],
    ) -> SaveStandaloneScript:
        return SaveStandaloneScript(SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session))

    def approve_lesson(
        session: Annotated[Session, Depends(operation_session)],
    ) -> lessons_uc.ApproveStandaloneLesson:
        return lessons_uc.ApproveStandaloneLesson(
            SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session)
        )

    def standalone_storyboard(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStandaloneStoryboard:
        return GenerateStandaloneStoryboard(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            selected_storyboard(model_override),
            tracking=tracking() if tracking else None,
            memories=SqlAlchemyGuideRepository(session),
            quiz_jobs=background_quizzes(session, model_override),
        )

    def standalone_speech(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStandaloneSpeech:
        synthesizer, artifacts, settings, gap = speech()
        return GenerateStandaloneSpeech(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            synthesizer,
            artifacts,
            settings,
            gap,
            tracking=tracking() if tracking else None,
        )

    def standalone_animation(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStandaloneAnimation:
        return GenerateStandaloneAnimation(
            SqlAlchemyStandaloneLessons(session),
            CourseUnitOfWork(session),
            animator(),
            speech()[1],
            tracking=tracking() if tracking else None,
            memories=SqlAlchemyGuideRepository(session),
        )

    app.dependency_overrides.update(
        {
            http.get_owner: owner,
            http.get_create: create_lesson,
            http.get_copy: copy_lesson,
            http.get_update: update_lesson,
            http.get_list: list_lessons,
            http.get_lesson: read_lesson,
            http.get_plan: plan_lesson,
            http.get_approve: approve_lesson,
            outline_http.get_save_outline: save_outline,
            http.get_save_script: save_script,
            http.get_storyboard: standalone_storyboard,
            http.get_speech: standalone_speech,
            http.get_animation: standalone_animation,
        }
    )

    def generator(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateSyllabus:
        return build_syllabus_services(
            session,
            selected_syllabus(model_override),
            tracking() if tracking else None,
            selected_style(model_override),
            voice_catalog() if voice_catalog else None,
        )[0]

    def syllabus_session(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GetSyllabusSession:
        return build_syllabus_services(session, selected_syllabus(model_override))[1]

    def lesson_generator(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateLesson:
        return GenerateLesson(
            MySqlCourseRepository(session),
            SqlAlchemySyllabusConversations(session),
            selected_lesson(model_override),
            CourseUnitOfWork(session),
            tracking=tracking() if tracking else None,
            thumbnail_jobs=background_thumbnails(session),
            memories=SqlAlchemyGuideRepository(session),
        )

    def storyboard_generator(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStoryboard:
        return GenerateStoryboard(
            MySqlCourseRepository(session),
            SqlAlchemySyllabusConversations(session),
            selected_storyboard(model_override),
            CourseUnitOfWork(session),
            tracking=tracking() if tracking else None,
            memories=SqlAlchemyGuideRepository(session),
        )

    def speech_generator(session: Annotated[Session, Depends(operation_session)]) -> GenerateSpeech:
        synthesizer, artifacts, settings, gap = speech()
        return GenerateSpeech(
            MySqlCourseRepository(session),
            synthesizer,
            artifacts,
            settings,
            CourseUnitOfWork(session),
            gap,
            tracking=tracking() if tracking else None,
        )

    def animation_generator(
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateAnimation:
        return GenerateAnimation(
            MySqlCourseRepository(session),
            SqlAlchemySyllabusConversations(session),
            animator(),
            speech()[1],
            CourseUnitOfWork(session),
            tracking=tracking() if tracking else None,
            memories=SqlAlchemyGuideRepository(session),
        )

    def speech_reader(session: Annotated[Session, Depends(operation_session)]) -> GetSpeechArtifact:
        return GetSpeechArtifact(
            MySqlCourseRepository(session), speech()[1], CourseUnitOfWork(session)
        )

    def standalone_script(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStandaloneScript:
        return GenerateStandaloneScript(
            approve_lesson(session),
            standalone_storyboard(model_override, session),
        )

    def automatic_lesson(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateAutomaticLesson:
        return GenerateAutomaticLesson(
            plan_lesson(model_override, session), standalone_video(model_override, session)
        )

    def standalone_video(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateStandaloneVideo:
        return GenerateStandaloneVideo(
            approve_lesson(session),
            standalone_storyboard(model_override, session),
            standalone_speech(session),
            standalone_animation(session),
        )

    def course_video(
        model_override: Annotated[AnimatorModel | None, Depends(generation_model)],
        session: Annotated[Session, Depends(operation_session)],
    ) -> GenerateCourseVideo:
        return GenerateCourseVideo(
            lesson_generator(model_override, session),
            storyboard_generator(model_override, session),
            speech_generator(session),
            animation_generator(session),
        )

    app.dependency_overrides.update(
        {
            get_activity: lambda: RequestActivity(redis()),
            get_standalone_video: standalone_video,
            get_automatic_lesson: automatic_lesson,
            get_standalone_script: standalone_script,
            get_course_video: course_video,
        }
    )

    def courses(session: Annotated[Session, Depends(operation_session)]) -> CourseServices:
        return build_courses(
            session,
            tracking=tracking() if tracking else None,
            thumbnail_jobs=background_thumbnails(session),
        )

    def assets(session: Annotated[Session, Depends(operation_session)]) -> AssetServices:
        configured = storage()
        if configured is None:
            raise HTTPException(503, "Cloud Storage is not configured")
        return build_assets(session, configured)

    def catalog() -> CatalogServices:
        return CatalogServices(GetCatalog(RedisCatalog(redis())))

    if spend is not None and billing is not None:
        from app.courses.adapters.http.internal_tools import get_inspector
        from app.courses.application.inspect_lesson import InspectLesson

        def inspector(session: Annotated[Session, Depends(get_session)]) -> InspectLesson:
            return InspectLesson(
                SqlAlchemyStandaloneLessons(session),
                MySqlCourseRepository(session),
                CourseUnitOfWork(session),
                spend(),
                billing(),
                SystemClock(),
            )

        app.dependency_overrides[get_inspector] = inspector

        def standalone_spend_reader(
            session: Annotated[Session, Depends(operation_session)],
        ) -> GetStandaloneSpend:
            return GetStandaloneSpend(
                SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session), spend()
            )

        def standalone_spend_refresher(
            session: Annotated[Session, Depends(operation_session)],
        ) -> RefreshStandaloneSpend:
            return RefreshStandaloneSpend(
                SqlAlchemyStandaloneLessons(session), CourseUnitOfWork(session), spend(), billing()
            )

        app.dependency_overrides.update(
            {
                http.get_spend_reader: standalone_spend_reader,
                http.get_spend_refresher: standalone_spend_refresher,
            }
        )

        def spend_reader(session: Annotated[Session, Depends(operation_session)]) -> GetCourseSpend:
            return GetCourseSpend(MySqlCourseRepository(session), spend())

        def spend_refresher(
            session: Annotated[Session, Depends(operation_session)],
        ) -> RefreshCourseSpend:
            return RefreshCourseSpend(
                MySqlCourseRepository(session), spend(), billing(), CourseUnitOfWork(session)
            )

        app.dependency_overrides.update(
            {get_spend_reader: spend_reader, get_spend_refresher: spend_refresher}
        )

    app.dependency_overrides.update(
        {
            get_courses: courses,
            get_assets: assets,
            get_catalog: catalog,
            get_generator: generator,
            get_lesson_generator: lesson_generator,
            get_storyboard_generator: storyboard_generator,
            get_speech_generator: speech_generator,
            get_animation_generator: animation_generator,
            get_speech_reader: speech_reader,
            get_syllabus_session: syllabus_session,
        }
    )


def build_lesson_agent(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    session_factory: AgentSessionFactory | None = None,
    mode: GenerationMode | None = None,
    model_override: AnimatorModel | None = None,
) -> LessonAgent:
    if mode is None:
        return RoutedLessonAgent(
            {
                choice: build_lesson_agent(
                    config,
                    tracking,
                    mode=choice,
                    model_override=model_override,
                    session_factory=session_factory,
                )
                for choice in GenerationMode
            }
        )
    profile = generation_profile(mode, model_override)
    from app.courses.adapters.ai.unconfigured_lesson import UnconfiguredLessonAgent

    if (
        not config.openrouter_api_key.get_secret_value()
        or not config.tavily_api_key.get_secret_value()
    ):
        return UnconfiguredLessonAgent()
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent
    from pydantic_ai.common_tools.tavily import tavily_search_tool
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider
    from tavily import AsyncTavilyClient

    from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
    from app.courses.adapters.ai.lesson import PydanticLessonAgent, prepare_search, validate_plan
    from app.courses.domain.lesson_plan import LessonPlan
    from app.courses.ports.lesson_agent import LessonAgentRequest

    prompt = Path(__file__).with_name("adapters").joinpath("ai/lesson_prompt.md").read_text()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Agent[LessonAgentRequest, LessonPlan]]:
        async with AsyncExitStack() as lifecycle:
            client = await lifecycle.enter_async_context(
                AsyncOpenAI(
                    api_key=config.openrouter_api_key.get_secret_value(),
                    base_url="https://openrouter.ai/api/v1",
                    max_retries=0,
                    http_client=DefaultAsyncHttpxClient(
                        event_hooks={
                            "request": [tracking.async_request],
                            "response": [tracking.async_response],
                        }
                        if tracking
                        else {}
                    ),
                )
            )
            search_client = AsyncTavilyClient(config.tavily_api_key.get_secret_value())
            lifecycle.push_async_callback(search_client.close)
            model = OpenAIResponsesModel(
                profile.model.removesuffix(":fast"),
                provider=OpenRouterProvider(openai_client=client),
            )
            agent = Agent(
                model,
                output_type=LessonPlan,
                deps_type=LessonAgentRequest,
                system_prompt=prompt,
                tools=[
                    replace(
                        tavily_search_tool(
                            client=search_client, max_results=5, search_depth="basic"
                        ),
                        prepare=prepare_search,
                    )
                ],
                retries=2,
                tool_timeout=20,
                model_settings=OpenAIResponsesModelSettings(
                    extra_body={
                        k: v for k, v in model_options(profile.model).items() if k != "model"
                    },
                    max_tokens=14000,
                    timeout=90,
                    openai_store=False,
                    parallel_tool_calls=False,
                    openai_reasoning_effort=profile.reasoning_effort,
                ),
            )
            agent.output_validator(validate_plan)
            yield agent

    return PydanticLessonAgent(scope, profile.model, PersistentAgentSessions(session_factory))


def build_storyboard_agent(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    session_factory: AgentSessionFactory | None = None,
    mode: GenerationMode | None = None,
    model_override: AnimatorModel | None = None,
) -> StoryboardAgent:
    if mode is None:
        return RoutedStoryboardAgent(
            {
                choice: build_storyboard_agent(
                    config,
                    tracking,
                    mode=choice,
                    model_override=model_override,
                    session_factory=session_factory,
                )
                for choice in GenerationMode
            }
        )
    profile = generation_profile(mode, model_override)
    from app.courses.adapters.ai.unconfigured_storyboard import UnconfiguredStoryboardAgent

    if not config.openrouter_api_key.get_secret_value():
        return UnconfiguredStoryboardAgent()
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent, RunContext
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
    from app.courses.adapters.ai.script import PydanticScriptAgent, ScriptOutput, validate_script
    from app.courses.adapters.ai.scripted_storyboard import ScriptedStoryboardAgent
    from app.courses.adapters.ai.storyboard import (
        PydanticStoryboardAgent,
        StoryboardOutput,
        validate_storyboard,
    )
    from app.courses.adapters.ai.visual_reference import storyboard_style_reference
    from app.courses.ports.script_agent import ScriptAgentRequest
    from app.courses.ports.storyboard_agent import VisualStoryboardRequest

    prompt = (Path(__file__).parent / "adapters/ai/storyboard_prompt.md").read_text()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Agent[VisualStoryboardRequest, StoryboardOutput]]:
        async with AsyncOpenAI(
            api_key=config.openrouter_api_key.get_secret_value(),
            base_url="https://openrouter.ai/api/v1",
            http_client=DefaultAsyncHttpxClient(
                event_hooks={
                    "request": [tracking.async_request],
                    "response": [tracking.async_response],
                }
                if tracking
                else {}
            ),
            max_retries=0,
        ) as client:
            agent = Agent(
                OpenAIResponsesModel(
                    profile.model.removesuffix(":fast"),
                    provider=OpenRouterProvider(openai_client=client),
                ),
                output_type=StoryboardOutput,
                deps_type=VisualStoryboardRequest,
                system_prompt=prompt,
                retries=2,
                model_settings=OpenAIResponsesModelSettings(
                    extra_body={
                        k: v for k, v in model_options(profile.model).items() if k != "model"
                    },
                    max_tokens=24000,
                    openai_reasoning_effort=profile.reasoning_effort,
                    timeout=180,
                    openai_store=False,
                    parallel_tool_calls=False,
                ),
            )

            @agent.system_prompt(dynamic=True)
            def selected_visual_reference(ctx: RunContext[VisualStoryboardRequest]) -> str:
                return storyboard_style_reference(
                    Path(config.animator_tools_directory),
                    ctx.deps.visual_style_id,
                    ctx.deps.visual_style_version,
                    asdict(ctx.deps.script),
                )

            agent.output_validator(validate_storyboard)
            yield agent

    @asynccontextmanager
    async def script_scope() -> AsyncIterator[Agent[ScriptAgentRequest, ScriptOutput]]:
        async with AsyncOpenAI(
            api_key=config.openrouter_api_key.get_secret_value(),
            base_url="https://openrouter.ai/api/v1",
            http_client=DefaultAsyncHttpxClient(
                event_hooks={
                    "request": [tracking.async_request],
                    "response": [tracking.async_response],
                }
                if tracking
                else {}
            ),
            max_retries=0,
        ) as client:
            agent = Agent(
                OpenAIResponsesModel(
                    profile.model.removesuffix(":fast"),
                    provider=OpenRouterProvider(openai_client=client),
                ),
                output_type=ScriptOutput,
                deps_type=ScriptAgentRequest,
                system_prompt=(Path(__file__).parent / "adapters/ai/script_prompt.md").read_text(),
                retries=2,
                model_settings=OpenAIResponsesModelSettings(
                    extra_body={
                        k: v for k, v in model_options(profile.model).items() if k != "model"
                    },
                    max_tokens=24000,
                    openai_reasoning_effort=profile.reasoning_effort,
                    timeout=180,
                    openai_store=False,
                    parallel_tool_calls=False,
                ),
            )
            agent.output_validator(validate_script)
            yield agent

    return ScriptedStoryboardAgent(
        PydanticScriptAgent(script_scope, profile.model, PersistentAgentSessions(session_factory)),
        PydanticStoryboardAgent(
            scope,
            profile.model,
            PersistentAgentSessions(session_factory),
            tools=Path(config.animator_tools_directory),
        ),
        tracking=tracking,
        tools=Path(config.animator_tools_directory),
    )


def build_speech(
    config: Settings,
    lifecycle: ExitStack,
    tracking: ProviderUsageTracking | None = None,
) -> tuple[SpeechSynthesizer, SpeechArtifacts, SpeechSettings, float]:
    import google.auth
    from google.cloud.storage import Client  # type: ignore[import-untyped]

    from app.courses.adapters.ai.elevenlabs import ElevenLabsSpeech
    from app.courses.adapters.storage.speech import GcsSpeechArtifacts, LocalSpeechArtifacts

    client = lifecycle.enter_context(
        httpx.Client(
            base_url="https://api.elevenlabs.io",
            timeout=httpx.Timeout(120, connect=10),
            transport=httpx.HTTPTransport(retries=0),
            event_hooks={"request": [tracking.request], "response": [tracking.response]}
            if tracking
            else {},
        )
    )
    settings = SpeechSettings(
        config.elevenlabs_voice_id,
        config.speech_stability,
        config.speech_similarity,
        config.speech_clone_strength,
        delivery="American accent",
    )
    artifacts: SpeechArtifacts
    if config.speech_storage_backend == "gcs":
        if not config.gcs_bucket:
            raise ValueError("GCS speech storage requires COURSE_MAKER_GCS_BUCKET")
        credentials, project = google.auth.default(
            scopes=("https://www.googleapis.com/auth/cloud-platform",)
        )
        storage_client = Client(project=config.gcp_project or project, credentials=credentials)
        lifecycle.callback(storage_client.close)
        artifacts = GcsSpeechArtifacts(storage_client, config.gcs_bucket)
    else:
        artifacts = LocalSpeechArtifacts(Path(config.speech_local_directory))
    return (
        ElevenLabsSpeech(client, config.elevenlabs_api_key.get_secret_value()),
        artifacts,
        settings,
        config.speech_silence_between_scenes_sec,
    )


def build_animator(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    session_factory: AgentSessionFactory | None = None,
    mode: GenerationMode | None = None,
    animator_model: AnimatorModel | None = None,
    backend: AnimationBackend | None = None,
) -> Animator:
    from app.courses.adapters.ai.canvas_delivery import CanvasDelivery
    from app.courses.adapters.ai.canvas_production import CanvasProduction
    from app.courses.application.produce_canvas_animation import ProduceCanvasAnimation

    if mode is None:
        return RoutedAnimator(
            {
                choice: build_animator(
                    config, tracking, mode=choice, backend=backend, session_factory=session_factory
                )
                for choice in GenerationMode
            },
            {
                (choice, model): build_animator(
                    config,
                    tracking,
                    mode=choice,
                    animator_model=model,
                    backend=backend,
                    session_factory=session_factory,
                )
                for choice in GenerationMode
                for model in AnimatorModel
            },
        )
    profile = generation_profile(mode, animator_model)
    root, tools = Path(config.animation_local_directory), Path(config.animator_tools_directory)
    model = profile.model
    from app.courses.adapters.ai.direct_animation import (
        DirectAnimationCall,
        DirectCanvasAnimator,
        DirectCanvasReviewer,
    )

    def direct_client() -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(config.animator_timeout_sec, connect=15),
            event_hooks={"request": [tracking.request], "response": [tracking.response]}
            if tracking
            else {},
        )

    llm = DirectAnimationCall(
        direct_client,
        config.openrouter_api_key.get_secret_value(),
        model,
        profile.reasoning_effort,
        tracking,
        session_factory=session_factory,
    )
    animator = DirectCanvasAnimator(
        root,
        tools,
        config.openrouter_api_key.get_secret_value(),
        model,
        config.animator_image,
        config.animator_timeout_sec,
        config.animator_max_attempts,
        tracking=tracking,
        reasoning_effort=profile.reasoning_effort,
        llm=llm,
    )
    reviewer = DirectCanvasReviewer(llm)
    renderer = AnimationWorker(
        root,
        tools,
        "",
        profile.model,
        config.lesson_video_image,
        config.animator_timeout_sec,
        tracking=tracking,
    )
    delivery = CanvasDelivery(
        root,
        reviewer.arguments(),
        reviewer.run_job,
        renderer.run_job,
        config.lesson_video_image,
    )
    from app.courses.adapters.ai.animation_elements import StoryboardElementAgent

    element_llm = DirectAnimationCall(
        direct_client,
        config.openrouter_api_key.get_secret_value(),
        model,
        profile.reasoning_effort,
        tracking,
        session_factory=session_factory,
        max_output_tokens=16000,
    )
    return CanvasProduction(
        ProduceCanvasAnimation(
            animator,
            delivery,
            StoryboardElementAgent(root, tools, element_llm),
        ),
        animator,
    )


def seed_constitution_smoke(
    env_file: Path, fixture: Path, database_url: str | None, reset_storyboard: bool = False
) -> str:
    """Developer-only composition: seed a fixed brief without calling the syllabus agent.

    Re-running preserves generated artifacts and spend; paid generation remains explicit.
    """
    import json

    from pydantic import TypeAdapter
    from sqlalchemy import create_engine

    from app.courses.adapters.persistence.codec import decode
    from app.courses.domain.curriculum import Curriculum
    from app.courses.ports.syllabus_agent import SyllabusConversation

    data = json.loads(fixture.read_text())
    course = decode(data["course"])
    curriculum = TypeAdapter(Curriculum).validate_python(data["curriculum"])
    url = database_url or Settings(_env_file=env_file).database_url  # type: ignore[call-arg]
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            courses = MySqlCourseRepository(session)
            existing = courses.get_by_id(course.id)
            if existing is None:
                courses.add(course)
                session.flush()
                SqlAlchemySyllabusConversations(session).save(
                    SyllabusConversation(str(course.id), 1, curriculum=curriculum), 0
                )
            elif reset_storyboard:
                chapters = tuple(
                    replace(
                        chapter,
                        lessons=tuple(
                            replace(
                                lesson,
                                storyboard=None,
                                storyboard_generation=None,
                                alignment=None,
                                animation=None,
                                video_url=None,
                                video_asset_id=None,
                                quiz=(),
                            )
                            for lesson in chapter.lessons
                        ),
                    )
                    for chapter in existing.chapters
                )
                courses.save(replace(existing, chapters=chapters))
                conversations = SqlAlchemySyllabusConversations(session)
                state = conversations.get_by_course_id(course.id)
                if state is None:
                    raise ValueError("Smoke course is missing its saved guide")
                conversations.save(
                    replace(state, revision=state.revision + 1, curriculum=curriculum),
                    state.revision,
                )
    finally:
        engine.dispose()
    return str(course.id)


def build_style(
    config: Settings, lifecycle: ExitStack, tracking: ProviderUsageTracking | None = None
) -> tuple[StylePlanner | None, VoiceCatalog]:
    from app.courses.adapters.ai.style import ElevenLabsVoices, OpenRouterStylePlanner

    def client(base_url: str) -> httpx.Client:
        return lifecycle.enter_context(
            httpx.Client(
                base_url=base_url,
                timeout=httpx.Timeout(120, connect=10),
                event_hooks={"request": [tracking.request], "response": [tracking.response]}
                if tracking
                else {},
            )
        )

    planner = (
        OpenRouterStylePlanner(
            client("https://openrouter.ai"), config.openrouter_api_key.get_secret_value()
        )
        if config.openrouter_api_key.get_secret_value()
        else None
    )
    voices = ElevenLabsVoices(
        client("https://api.elevenlabs.io"),
        config.elevenlabs_api_key.get_secret_value(),
        VoiceOption(config.elevenlabs_voice_id, "Configured narrator"),
    )
    return planner, voices


def build_thumbnails(
    config: Settings, lifecycle: ExitStack, tracking: ProviderUsageTracking | None = None
) -> ThumbnailGenerator | None:
    from app.courses.adapters.ai.thumbnails import OpenRouterThumbnails

    if not config.openrouter_api_key.get_secret_value():
        return None
    directory = Path(__file__).parent / "adapters" / "ai"
    prompt = (directory / "thumbnail_prompt.md").read_text()
    prompt += "\n".join(
        (directory / "thumbnail_examples" / f"{name}.svg").read_text()
        for name in ("inertia", "history", "math")
    )
    client = lifecycle.enter_context(
        httpx.Client(
            base_url="https://openrouter.ai",
            timeout=httpx.Timeout(90, connect=10),
            event_hooks={"request": [tracking.request], "response": [tracking.response]}
            if tracking
            else {},
        )
    )
    return OpenRouterThumbnails(
        client, config.openrouter_api_key.get_secret_value(), config.thumbnail_model, prompt
    )


def build_guide_agent(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    mode: GenerationMode = GenerationMode.BALANCED,
    model_override: AnimatorModel | None = None,
) -> "GuideAgent":
    from app.courses.adapters.ai.unconfigured_guide import UnconfiguredGuideAgent

    if not config.openrouter_api_key.get_secret_value():
        return UnconfiguredGuideAgent()
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from app.courses.adapters.ai.guide import (
        GUIDE_TOOLS,
        GuideRunDependencies,
        PydanticGuideAgent,
        current_guide_context,
    )

    prompt_directory = Path(__file__).with_name("adapters").joinpath("ai")
    prompt = (prompt_directory / "guide_prompt.md").read_text()
    prompt += "\n" + (prompt_directory / "answer_prompt.md").read_text()

    @asynccontextmanager
    async def scope(
        selected_mode: GenerationMode,
    ) -> AsyncIterator[tuple[Agent[GuideRunDependencies, str], Agent[None, str]]]:
        profile = generation_profile(selected_mode, model_override)
        async with AsyncOpenAI(
            api_key=config.openrouter_api_key.get_secret_value(),
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            http_client=DefaultAsyncHttpxClient(
                event_hooks={
                    "request": [tracking.async_request],
                    "response": [tracking.async_response],
                }
                if tracking
                else {}
            ),
        ) as client:
            model = OpenAIResponsesModel(
                profile.model.removesuffix(":fast"),
                provider=OpenRouterProvider(openai_client=client),
            )
            settings = OpenAIResponsesModelSettings(
                extra_body={k: v for k, v in model_options(profile.model).items() if k != "model"},
                max_tokens=6000,
                timeout=120,
                openai_store=False,
                parallel_tool_calls=False,
                openai_reasoning_effort=profile.reasoning_effort,
            )
            agent = Agent(
                model,
                deps_type=GuideRunDependencies,
                output_type=str,
                instructions=[prompt, current_guide_context],
                tools=GUIDE_TOOLS,
                model_settings=settings,
                retries=2,
            )
            summarizer = Agent(
                model,
                output_type=str,
                instructions="Summarize faithfully; preserve decisions and references.",
                model_settings=OpenAIResponsesModelSettings(
                    extra_body={
                        k: v for k, v in model_options(profile.model).items() if k != "model"
                    },
                    max_tokens=3000,
                    timeout=90,
                    openai_reasoning_effort=profile.reasoning_effort,
                    openai_store=False,
                ),
            )
            yield agent, summarizer

    return PydanticGuideAgent(scope)


def build_quiz_agent(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    session_factory: AgentSessionFactory | None = None,
    mode: GenerationMode | None = None,
    model_override: AnimatorModel | None = None,
) -> QuizAgent:
    from app.courses.adapters.ai.unconfigured_quiz import UnconfiguredQuizAgent

    if not config.openrouter_api_key.get_secret_value():
        return UnconfiguredQuizAgent()
    if mode is None:
        return RoutedQuizAgent(
            {
                choice: build_quiz_agent(
                    config,
                    tracking,
                    mode=choice,
                    model_override=model_override,
                    session_factory=session_factory,
                )
                for choice in GenerationMode
            }
        )
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
    from app.courses.adapters.ai.quiz import PydanticQuizAgent, QuizDraft, validate_quiz

    profile = generation_profile(mode, model_override)
    prompt = Path(__file__).with_name("adapters").joinpath("ai/quiz_prompt.md").read_text()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Agent[QuizAgentRequest, QuizDraft]]:
        async with AsyncOpenAI(
            api_key=config.openrouter_api_key.get_secret_value(),
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            http_client=DefaultAsyncHttpxClient(
                event_hooks={
                    "request": [tracking.async_request],
                    "response": [tracking.async_response],
                }
                if tracking
                else {}
            ),
        ) as client:
            agent = Agent(
                OpenAIResponsesModel(
                    profile.model.removesuffix(":fast"),
                    provider=OpenRouterProvider(openai_client=client),
                ),
                output_type=QuizDraft,
                deps_type=QuizAgentRequest,
                system_prompt=prompt,
                retries=2,
                model_settings=OpenAIResponsesModelSettings(
                    extra_body=model_options(profile.model),
                    openai_reasoning_effort=profile.reasoning_effort,
                ),
            )
            agent.output_validator(validate_quiz)
            yield agent

    return PydanticQuizAgent(scope, PersistentAgentSessions(session_factory))


def build_interactive_agent(
    config: Settings,
    tracking: ProviderUsageTracking | None = None,
    *,
    session_factory: AgentSessionFactory | None = None,
    mode: GenerationMode | None = None,
    model_override: AnimatorModel | None = None,
) -> InteractiveAgent:
    from app.courses.adapters.ai.unconfigured_interactive import UnconfiguredInteractiveAgent

    if not config.openrouter_api_key.get_secret_value():
        return UnconfiguredInteractiveAgent()
    from app.courses.adapters.ai.interactive import RoutedInteractiveAgent

    if mode is None:
        return RoutedInteractiveAgent(
            {
                choice: build_interactive_agent(
                    config,
                    tracking,
                    mode=choice,
                    model_override=model_override,
                    session_factory=session_factory,
                )
                for choice in GenerationMode
            }
        )
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from app.courses.adapters.ai.agent_sessions import PersistentAgentSessions
    from app.courses.adapters.ai.interactive import (
        InteractiveDraft,
        PydanticInteractiveAgent,
        validate_interactive,
    )

    profile = generation_profile(mode, model_override)
    prompt = Path(__file__).with_name("adapters").joinpath("ai/interactive_prompt.md").read_text()

    @asynccontextmanager
    async def scope() -> AsyncIterator[Agent[InteractiveAgentRequest, InteractiveDraft]]:
        async with AsyncOpenAI(
            api_key=config.openrouter_api_key.get_secret_value(),
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            http_client=DefaultAsyncHttpxClient(
                event_hooks={
                    "request": [tracking.async_request],
                    "response": [tracking.async_response],
                }
                if tracking
                else {}
            ),
        ) as client:
            agent = Agent(
                OpenAIResponsesModel(
                    profile.model.removesuffix(":fast"),
                    provider=OpenRouterProvider(openai_client=client),
                ),
                output_type=InteractiveDraft,
                deps_type=InteractiveAgentRequest,
                system_prompt=prompt,
                retries=2,
                model_settings=OpenAIResponsesModelSettings(
                    extra_body=model_options(profile.model),
                    openai_reasoning_effort=profile.reasoning_effort,
                ),
            )
            agent.output_validator(validate_interactive)
            yield agent

    return PydanticInteractiveAgent(scope, PersistentAgentSessions(session_factory))


def build_agent_session_factory(sessions: Callable[[], Session]) -> AgentSessionFactory:
    from contextlib import contextmanager

    from app.courses.adapters.persistence.agent_sessions import SqlAlchemyAgentSessions

    @contextmanager
    def scope() -> Iterator[RunAgentSession]:
        with sessions() as session:
            yield RunAgentSession(
                SqlAlchemyAgentSessions(session), CourseUnitOfWork(session), UuidIdGenerator()
            )

    return scope
