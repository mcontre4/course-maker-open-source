"""Real production course wiring with isolated SQL and deterministic media storage."""

from collections.abc import Iterator
from types import SimpleNamespace

from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.courses.adapters.http import creators, learning_activity, standalone
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.http.router import router as courses_router
from app.courses.composition import install_dependencies
from app.shared.infrastructure.database import get_session
from app.shared.infrastructure.http import register_http_handlers


class LocalMediaStorage:
    def __init__(self):
        self.downloads = []

    def download_url(self, object_name):
        self.downloads.append(object_name)
        return "http://127.0.0.1:50120/test-video.mp4"

    def upload_url(self, object_name, content_type, size):
        return "http://127.0.0.1:50120/test-video.mp4"


def create_creator_test_app(sessions, storage):
    app = FastAPI()
    app.state.settings = SimpleNamespace(
        api_key=SecretStr("creator-e2e-test-secret"),
        animation_local_directory="/unused-test-artifacts",
        lesson_video_image="test-renderer",
    )
    app.include_router(creators.router)
    app.include_router(learning_activity.router)
    app.include_router(standalone.router)
    app.include_router(courses_router)
    register_error_handlers(app)
    register_http_handlers(app)
    install_dependencies(
        app,
        lambda: storage,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
    )

    def session() -> Iterator[Session]:
        with sessions() as scoped:
            yield scoped

    app.dependency_overrides[get_session] = session
    return app
