from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.http.lesson_interactive import public_router, router
from app.courses.adapters.http.router import router as course_router
from app.courses.adapters.http.standalone import router as lesson_router
from app.courses.composition import install_dependencies
from app.shared.infrastructure.database import get_session
from app.shared.infrastructure.http import authorize
from app.shared.infrastructure.settings import Settings

TEST_KEY = "interactive-test-secret-0123456789"
HEADERS = {"Authorization": f"Bearer {TEST_KEY}"}


def interactive_test_app(engine, agent, workers, tracking=None, settings=None):
    app = FastAPI()
    app.state.settings = settings or Settings(
        _env_file=None,
        database_url="mysql+pymysql://unused:unused@localhost/unused",
        api_key=TEST_KEY,
    )

    def session():
        with Session(engine) as scoped:
            yield scoped

    install_dependencies(
        app,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
        lambda: None,
        interactive_agent=lambda: agent,
        interactive_workers=lambda: workers,
        tracking=(lambda: tracking) if tracking else None,
    )
    app.dependency_overrides[get_session] = session
    register_error_handlers(app)
    app.include_router(public_router)
    for routes in (router, lesson_router, course_router):
        app.include_router(routes, dependencies=[Depends(authorize)])
    return app


def create_interactive_lesson(client):
    response = client.post(
        "/api/v1/lessons",
        json={
            "title": "Gravity",
            "description": "Explore a pendulum",
            "minutes": 1,
            "style": {"visualStyleId": "flat-vector-science", "audience": "Beginners"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
