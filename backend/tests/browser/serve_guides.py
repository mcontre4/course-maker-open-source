"""Disposable full-stack browser test server. Never uses a developer database or AI key."""

import hashlib
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated

import uvicorn
from fakes.browser_media import BrowserLessonMedia
from fakes.guide_model import GuideModelScript
from fakes.lesson_interactive import RecordingInteractiveAgent
from fakes.spend import FixedBilling
from fastapi import Depends, Header
from fixtures.guide_app import build_guide_test_app
from fixtures.public_content import seed_public_content
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.courses.adapters.ai.animation_project import project_digest
from app.courses.adapters.http.internal_tools import get_inspector
from app.courses.adapters.http.internal_tools import router as internal_router
from app.courses.adapters.http.standalone import get_owner
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.inspect_lesson import InspectLesson
from app.courses.domain.spend import GenerationStep, ModelCharge
from app.shared.infrastructure.database import Base, get_session
from app.shared.infrastructure.system_clock import SystemClock


def main():
    with (
        PostgresContainer("postgres:16-alpine", driver="psycopg") as container,
        RedisContainer("redis:7.4-alpine") as cache,
        ThreadPoolExecutor(max_workers=2) as interactive_workers,
    ):
        engine = create_engine(container.get_connection_url(), pool_pre_ping=True)
        try:
            fixture = Path(__file__).parents[1] / "fixtures/public-video.mp4"
            app, _ = build_guide_test_app(
                engine,
                GuideModelScript(),
                media=BrowserLessonMedia(fixture),
                interactive_agent=RecordingInteractiveAgent(),
                interactive_workers=interactive_workers,
                redis_client=Redis.from_url(
                    f"redis://{cache.get_container_host_ip()}:{cache.get_exposed_port(6379)}/0",
                    decode_responses=True,
                ),
            )

            def browser_owner(
                x_test_owner: str = Header(default="user_00000000-0000-0000-0000-000000000001"),
            ):
                return x_test_owner

            app.dependency_overrides[get_owner] = browser_owner
            ledger = SqlSpendRepository(sessionmaker(engine))

            def inspector(scoped: Annotated[Session, Depends(get_session)]):
                return InspectLesson(
                    SqlAlchemyStandaloneLessons(scoped),
                    MySqlCourseRepository(scoped),
                    CourseUnitOfWork(scoped),
                    ledger,
                    FixedBilling(),
                    SystemClock(),
                )

            app.dependency_overrides[get_inspector] = inspector
            app.include_router(internal_router)

            # The credits UI is separate from these content suites. Pin its read-only
            # balance while the production credit API is being built.
            @app.get("/api/v1/credits")
            def fixture_credit_balance():
                return {"credits": 100}

            @app.get("/api/v1/auth/config")
            def fixture_auth_mode():
                return {"enabled": False}

            @app.get("/api/v1/auth/session")
            def fixture_account():
                # Existing content suites use a pinned owner. Account flows have a
                # separate server exercising production auth, SMTP, Redis and migrations.
                return {
                    "user": {
                        "id": "user_00000000-0000-0000-0000-000000000001",
                        "email": "browser@example.com",
                        "first_name": "Browser",
                        "last_name": "Learner",
                        "verified": True,
                    },
                    "csrf_token": "content-suite-csrf",
                    "google_enabled": False,
                }

            Base.metadata.create_all(engine)
            with tempfile.TemporaryDirectory(prefix="public-discovery-e2e-") as directory:
                root = Path(directory)
                app.state.settings = SimpleNamespace(
                    animation_local_directory=directory,
                    lesson_video_image="browser-test-v1",
                    internal_tools_key=SecretStr("browser-internal-tools-key-32-characters"),
                )
                with Session(engine) as session:
                    course, lesson, _ = seed_public_content(session)
                    source = root / lesson.animation.project_key
                    source.mkdir(parents=True)
                    (source / "scene.js").write_text("// Deterministic browser playback fixture")
                    project = replace(lesson.animation, output_hash=project_digest(source))
                    courses = MySqlCourseRepository(session)
                    courses.save(
                        course._replace_lesson(
                            replace(course.chapters[0].lessons[0], animation=project)
                        )
                    )
                    lessons = SqlAlchemyStandaloneLessons(session)
                    item = lessons.require_by_id(lesson.id)
                    lessons.save(replace(item, content=replace(item.content, animation=project)))
                    session.commit()
                for scope in (None, str(course.id)):
                    suffix = "standalone" if scope is None else "course"
                    ledger.save(
                        ModelCharge(
                            f"charge_internal_{suffix}",
                            scope,
                            str(lesson.id),
                            "lesson",
                            "openrouter",
                            "fixture-model",
                            usd=Decimal("0.1234"),
                            input_tokens=100,
                            output_tokens=50,
                        )
                    )
                    ledger.save(
                        ModelCharge(
                            f"charge_internal_pending_{suffix}",
                            scope,
                            str(lesson.id),
                            "speech",
                            "elevenlabs",
                            "fixture-voice",
                            credits=Decimal("10"),
                        )
                    )
                    for index, (stage, start, end) in enumerate(
                        [
                            ("lesson", 100, 160),
                            ("speech", 150, 180),
                            ("render", 200, 230),
                        ]
                    ):
                        ledger.save_step(
                            GenerationStep(
                                f"step_internal_{suffix}_{index}",
                                scope,
                                str(lesson.id),
                                stage,
                                start,
                                end,
                            )
                        )
                ledger.save_step(
                    GenerationStep(
                        "step_internal_running",
                        None,
                        "lesson_00000000-0000-0000-0000-000000000098",
                        "animation",
                        SystemClock().now().timestamp() - 3,
                    )
                )
                video_key = ".reviews/" + "c" * 64 + "/render/lesson.mp4"
                cache = (root / video_key).parent
                cache.mkdir(parents=True)
                fixture = Path(__file__).parents[1] / "fixtures/public-video.mp4"
                (cache / "lesson.mp4").write_bytes(fixture.read_bytes())
                report = {
                    "approved": False,
                    "review_status": "skipped",
                    "validation": "technical_validated",
                    "source_hash": project.output_hash,
                    "renderer_version": "browser-test-v1",
                    "video_key": video_key,
                    "video_sha256": hashlib.sha256((cache / "lesson.mp4").read_bytes()).hexdigest(),
                }
                decision = root / ".review-state" / ("d" * 64) / "result.json"
                decision.parent.mkdir(parents=True)
                decision.write_text(json.dumps(report))
                uvicorn.run(app, host="127.0.0.1", port=5181)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
