"""Composition root: infrastructure lifecycle, domain wiring, and HTTP application assembly."""

from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Annotated

import google.auth
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from google.auth import credentials, iam
from google.auth.credentials import Signing
from google.auth.transport.requests import Request as GoogleRequest
from google.cloud.storage import Client  # type: ignore[import-untyped]
from google.oauth2 import service_account
from redis import Redis
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.courses.adapters.ai.spend import ProviderBilling, ProviderUsageTracking
from app.courses.adapters.http.activity import (
    ERROR_HEADER,
    HEADER,
    THUMBNAIL_HEADER,
    track_activity,
)
from app.courses.adapters.http.creators import router as creator_router
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.http.internal_tools import router as internal_tools_router
from app.courses.adapters.http.learning_activity import router as learning_activity_router
from app.courses.adapters.http.lesson_interactive import public_router as public_interactive_router
from app.courses.adapters.http.lesson_interactive import router as interactive_router
from app.courses.adapters.http.lesson_quiz import public_router as public_quiz_router
from app.courses.adapters.http.lesson_quiz import router as quiz_router
from app.courses.adapters.http.lesson_video import router as lesson_video_router
from app.courses.adapters.http.router import get_list_owner
from app.courses.adapters.http.router import router as course_router
from app.courses.adapters.http.standalone import get_owner
from app.courses.adapters.http.standalone import router as lesson_router
from app.courses.adapters.http.style import router as style_router
from app.courses.adapters.http.thumbnails import router as thumbnail_router
from app.courses.adapters.http.video import router as video_router
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.adapters.storage.gcs import GoogleCloudStorage
from app.courses.application.authorize_access import AuthorizeCourseAccess, AuthorizeCourseRequest
from app.courses.composition import (
    build_agent_session_factory,
    build_animator,
    build_interactive_agent,
    build_lesson_agent,
    build_quiz_agent,
    build_speech,
    build_storyboard_agent,
    build_style,
    build_syllabus_agent,
    build_thumbnails,
)
from app.courses.composition import install_dependencies as install_courses
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.animator import Animator
from app.courses.ports.lesson_agent import LessonAgent
from app.courses.ports.lesson_interactive import InteractiveAgent
from app.courses.ports.lesson_quiz import QuizAgent
from app.courses.ports.speech import SpeechArtifacts, SpeechSynthesizer
from app.courses.ports.storage import Storage
from app.courses.ports.storyboard_agent import StoryboardAgent
from app.courses.ports.style import StylePlanner, VoiceCatalog
from app.courses.ports.syllabus_agent import SyllabusAgent
from app.courses.ports.thumbnails import ThumbnailGenerator
from app.credits.ports.payments import Payments
from app.shared.application.get_readiness import GetReadiness
from app.shared.infrastructure.database import Base, get_session, verify_database_schema
from app.shared.infrastructure.http import (
    authorize,
    bearer,
    get_readiness,
    health_router,
    register_http_handlers,
)
from app.shared.infrastructure.readiness import InfrastructureReadinessProbe
from app.shared.infrastructure.settings import Settings
from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
from app.users.adapters.http.auth_headers import AuthHeadersMiddleware
from app.users.adapters.http.authentication import require_account
from app.users.adapters.http.authentication import router as auth_router
from app.users.adapters.http.router import user_router
from app.users.application.authentication import ProfileResponse
from app.users.composition import build_auth_runtime, install_authentication, start_account_mail
from app.users.composition import install_dependencies as install_users
from app.users.ports.authentication import GoogleIdentityProvider


@dataclass(frozen=True)
class ApplicationResources:
    engine: Engine
    sessions: sessionmaker[Session]
    redis: Redis
    storage: Storage | None
    syllabus_agent: SyllabusAgent
    lesson_agent: LessonAgent
    storyboard_agent: StoryboardAgent
    speech: tuple[SpeechSynthesizer, SpeechArtifacts, SpeechSettings, float]
    animator: Animator
    spend: SqlSpendRepository
    billing: ProviderBilling
    tracking: ProviderUsageTracking
    thumbnail_workers: ThreadPoolExecutor
    style_planner: StylePlanner | None = None
    voice_catalog: VoiceCatalog | None = None
    thumbnails: ThumbnailGenerator | None = None
    quiz_agent: QuizAgent | None = None
    quiz_workers: ThreadPoolExecutor | None = None
    interactive_agent: InteractiveAgent | None = None
    interactive_workers: ThreadPoolExecutor | None = None


def _signing_credentials(
    config: Settings, source: credentials.Credentials, lifecycle: ExitStack
) -> credentials.Credentials:
    if config.gcs_signer_email:
        request = GoogleRequest()
        lifecycle.callback(request.session.close)
        signer = iam.Signer(request, source, config.gcs_signer_email)  # type: ignore[no-untyped-call]
        return service_account.Credentials(  # type: ignore[no-untyped-call]
            signer, config.gcs_signer_email, "https://oauth2.googleapis.com/token"
        )
    if not isinstance(source, Signing):
        raise ValueError("Configure COURSE_MAKER_GCS_SIGNER_EMAIL for keyless storage credentials")
    return source


def load_storage_credentials() -> tuple[credentials.Credentials, str | None]:
    return google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))


def _storage(config: Settings, lifecycle: ExitStack) -> Storage | None:
    if not config.gcs_bucket:
        return None
    credentials, project = load_storage_credentials()
    signing = _signing_credentials(config, credentials, lifecycle)
    client = Client(project=config.gcp_project or project, credentials=credentials)
    lifecycle.callback(client.close)
    return GoogleCloudStorage(client, config.gcs_bucket, signing)


@contextmanager
def _resources(
    config: Settings,
    lesson_agent: LessonAgent | None = None,
    storyboard_agent: StoryboardAgent | None = None,
    thumbnail_generator: ThumbnailGenerator | None = None,
    quiz_agent: QuizAgent | None = None,
    interactive_agent: InteractiveAgent | None = None,
) -> Iterator[ApplicationResources]:
    with ExitStack() as lifecycle:
        engine = create_engine(
            config.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
        )
        lifecycle.callback(engine.dispose)
        redis = Redis.from_url(
            config.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
        )
        lifecycle.callback(redis.close)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            verify_database_schema(
                connection,
                Base.metadata,
                excluded_tables=(
                    frozenset()
                    if config.auth_enabled
                    else frozenset(
                        {
                            "accounts",
                            "login_sessions",
                            "account_actions",
                            "account_mail_outbox",
                            "credit_accounts",
                            "credit_transactions",
                            "credit_checkouts",
                        }
                    )
                ),
            )
        sessions = sessionmaker(engine, expire_on_commit=False)
        session_factory = build_agent_session_factory(sessions)
        spend = SqlSpendRepository(sessions)
        billing_client = lifecycle.enter_context(httpx.Client(timeout=10))
        billing = ProviderBilling(
            billing_client,
            config.openrouter_api_key.get_secret_value(),
            config.elevenlabs_usd_per_credit,
        )
        tracking = ProviderUsageTracking(spend, billing)
        style_planner, voice_catalog = build_style(config, lifecycle, tracking)
        thumbnails = thumbnail_generator or build_thumbnails(config, lifecycle, tracking)
        thumbnail_workers = lifecycle.enter_context(ThreadPoolExecutor(max_workers=4))
        yield ApplicationResources(
            engine,
            sessions,
            redis,
            _storage(config, lifecycle),
            build_syllabus_agent(config, tracking, session_factory=session_factory),
            lesson_agent
            if lesson_agent is not None
            else build_lesson_agent(config, tracking, session_factory=session_factory),
            storyboard_agent
            or build_storyboard_agent(config, tracking, session_factory=session_factory),
            build_speech(config, lifecycle, tracking),
            build_animator(config, tracking, session_factory=session_factory),
            spend,
            billing,
            tracking,
            thumbnail_workers,
            style_planner,
            voice_catalog,
            thumbnails,
            quiz_agent or build_quiz_agent(config, tracking, session_factory=session_factory),
            lifecycle.enter_context(ThreadPoolExecutor(max_workers=2)),
            interactive_agent
            or build_interactive_agent(config, tracking, session_factory=session_factory),
            lifecycle.enter_context(ThreadPoolExecutor(max_workers=2)),
        )


def _install_dependencies(app: FastAPI) -> None:
    from app.credits.composition import install_dependencies as install_credits

    def session() -> Iterator[Session]:
        with app.state.resources.sessions() as scoped:
            yield scoped

    def readiness() -> GetReadiness:
        resources: ApplicationResources = app.state.resources
        probe = InfrastructureReadinessProbe(
            resources.engine, resources.redis, resources.storage is not None
        )
        return GetReadiness(probe)

    app.dependency_overrides.update({get_session: session, get_readiness: readiness})
    install_users(app)
    install_courses(
        app,
        lambda: app.state.resources.storage,
        lambda: app.state.resources.redis,
        lambda: app.state.resources.syllabus_agent,
        lambda: app.state.resources.lesson_agent,
        lambda: app.state.resources.storyboard_agent,
        lambda: app.state.resources.speech,
        lambda: app.state.resources.animator,
        lambda: app.state.resources.tracking,
        lambda: app.state.resources.spend,
        lambda: app.state.resources.billing,
        lambda: app.state.resources.style_planner,
        lambda: app.state.resources.voice_catalog,
        thumbnails=lambda: app.state.resources.thumbnails,
        thumbnail_workers=lambda: app.state.resources.thumbnail_workers,
        quiz_agent=lambda: app.state.resources.quiz_agent,
        quiz_workers=lambda: app.state.resources.quiz_workers,
        interactive_agent=lambda: app.state.resources.interactive_agent,
        interactive_workers=lambda: app.state.resources.interactive_workers,
        agent_sessions=lambda: build_agent_session_factory(app.state.resources.sessions),
    )
    install_authentication(app)

    install_credits(app)


def _install_credit_metering(app: FastAPI) -> None:
    if getattr(app.state, "credit_metering_installed", False):
        return
    from app.courses.adapters.http import (
        animation,
        lesson_interactive,
        lesson_quiz,
        lessons,
        speech,
        standalone,
        storyboards,
        style,
        syllabus,
        thumbnails,
        video,
    )
    from app.credits.composition import install_bundle_metering, install_metering

    install_metering(
        app,
        {
            standalone.get_create: "lesson_create",
            standalone.get_plan: "lesson_generate",
            standalone.get_storyboard: "lesson_media",
            standalone.get_speech: "lesson_media",
            standalone.get_animation: "lesson_media",
            video.get_standalone_script: "lesson_generate",
            video.get_automatic_lesson: "lesson_automatic",
            video.get_standalone_video: "lesson_automatic",
            video.get_course_video: "course_automatic",
            lessons.get_lesson_generator: "lesson_generate",
            storyboards.get_storyboard_generator: "lesson_media",
            speech.get_speech_generator: "lesson_media",
            animation.get_animation_generator: "lesson_media",
            lesson_quiz.generate_quiz: "lesson_regenerate",
            style.get_lesson_style: "lesson_generate",
            thumbnails.get_lesson_thumbnail: "lesson_regenerate",
            thumbnails.get_course_thumbnail: "course_generate",
            style.get_course_style: "course_generate",
            syllabus.get_generator: "course_generate",
        },
    )
    install_bundle_metering(
        app,
        lesson_interactive.get_interactives,
        {
            "create": "interactive_generate",
            "change": "interactive_generate",
            "retry": "interactive_generate",
        },
    )
    app.state.credit_metering_installed = True


def create_app(
    settings: Settings | None = None,
    *,
    lesson_agent: LessonAgent | None = None,
    storyboard_agent: StoryboardAgent | None = None,
    thumbnail_generator: ThumbnailGenerator | None = None,
    quiz_agent: QuizAgent | None = None,
    interactive_agent: InteractiveAgent | None = None,
    google_identity: GoogleIdentityProvider | None = None,
    payments: "Payments | None" = None,
) -> FastAPI:
    from app.courses.adapters.http.guide import router as guide_router
    from app.credits.adapters.http import router as credits_router
    from app.credits.composition import ScopedCreditBilling, build_payments, credit_costs

    cors_origins: list[str] = []

    def account_owner(profile: Annotated[ProfileResponse, Depends(require_account)]) -> str:
        return profile.id

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config = settings or Settings()  # type: ignore[call-arg]
        cors_origins[:] = config.cors_origins
        with _resources(
            config,
            lesson_agent,
            storyboard_agent,
            thumbnail_generator,
            quiz_agent,
            interactive_agent,
        ) as resources:
            app.state.settings, app.state.resources = config, resources
            with ExitStack() as auth_lifecycle:
                app.state.payments = payments or build_payments(config, auth_lifecycle)
                app.state.credit_billing = ScopedCreditBilling(
                    resources.sessions, credit_costs(config)
                )
                if config.auth_enabled:
                    app.state.auth = build_auth_runtime(
                        config,
                        resources.redis,
                        auth_lifecycle,
                        google_identity,
                    )
                    start_account_mail(config, resources.sessions, auth_lifecycle)
                    app.dependency_overrides[get_owner] = account_owner
                    app.dependency_overrides[get_list_owner] = account_owner
                    _install_credit_metering(app)

                yield

    app = FastAPI(title="Course Maker API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(AuthHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
        allow_credentials=True,
        expose_headers=[HEADER, ERROR_HEADER, THUMBNAIL_HEADER],
    )
    _install_dependencies(app)
    register_http_handlers(app)
    register_error_handlers(app)

    @app.get("/api/v1/auth/config")
    def authentication_mode(request: Request) -> dict[str, bool]:
        return {"enabled": request.app.state.settings.auth_enabled}

    def require_authentication_enabled(request: Request) -> None:
        if not request.app.state.settings.auth_enabled:
            raise HTTPException(404, "Not found")

    app.include_router(auth_router, dependencies=[Depends(require_authentication_enabled)])

    def credit_account_owner(
        request: Request,
        owner: Annotated[str, Depends(get_owner)],
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> str:
        if not request.app.state.settings.auth_enabled:
            authorize(request, credentials)
        return owner

    from app.credits.adapters.http import get_owner as get_credit_owner

    app.dependency_overrides[get_credit_owner] = credit_account_owner
    app.include_router(credits_router)

    def private_access(
        request: Request,
        owner: Annotated[str, Depends(get_owner)],
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session: Annotated[Session, Depends(get_session)],
    ) -> None:
        if not request.app.state.settings.auth_enabled:
            authorize(request, credentials)
            return
        course_id = request.path_params.get("course_id")
        if course_id:
            with SqlAlchemyUnitOfWork(session):
                AuthorizeCourseAccess(MySqlCourseRepository(session)).execute(
                    AuthorizeCourseRequest(course_id, owner)
                )

    app.include_router(internal_tools_router)
    app.include_router(creator_router)
    app.include_router(public_quiz_router)
    app.include_router(quiz_router, dependencies=[Depends(private_access)])
    app.include_router(public_interactive_router)
    app.include_router(interactive_router, dependencies=[Depends(private_access)])
    app.include_router(health_router)
    app.include_router(
        course_router,
        dependencies=[Depends(private_access), Depends(track_activity, scope="function")],
    )
    app.include_router(
        lesson_router,
        dependencies=[Depends(private_access), Depends(track_activity, scope="function")],
    )
    app.include_router(
        style_router,
        dependencies=[Depends(private_access), Depends(track_activity, scope="function")],
    )
    app.include_router(
        thumbnail_router,
        dependencies=[Depends(private_access), Depends(track_activity, scope="function")],
    )
    app.include_router(
        video_router,
        dependencies=[Depends(private_access), Depends(track_activity, scope="function")],
    )
    app.include_router(lesson_video_router, dependencies=[Depends(private_access)])
    app.include_router(guide_router, dependencies=[Depends(private_access)])
    app.include_router(learning_activity_router, dependencies=[Depends(private_access)])
    app.include_router(user_router, dependencies=[Depends(authorize)])
    return app


app = create_app()
