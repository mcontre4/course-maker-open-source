from dataclasses import replace

from fastapi import FastAPI
from fixtures.lesson_plan import lesson_plan
from sqlalchemy.orm import Session

from app.courses.adapters.ai.unconfigured_quiz import UnconfiguredQuizAgent
from app.courses.adapters.http.creators import router as creator_router
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.http.lesson_quiz import public_router, router
from app.courses.adapters.http.standalone import router as lesson_router
from app.courses.adapters.http.video import router as video_router
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.composition import install_dependencies
from app.courses.domain.identifiers import LessonId
from app.shared.infrastructure.database import get_session
from app.shared.infrastructure.settings import Settings


def quiz_test_app(
    engine, redis, agent=None, tracking=None, workers=None, storyboard=None, settings=None
):
    app = FastAPI()
    app.state.settings = settings or Settings(
        _env_file=None,
        database_url="mysql+pymysql://unused:unused@localhost/unused",
        api_key="lesson-quiz-test-secret-0123456789",
    )

    def session():
        with Session(engine) as scoped:
            yield scoped

    install_dependencies(
        app,
        lambda: None,
        lambda: redis,
        lambda: None,
        lambda: None,
        lambda: storyboard,
        lambda: None,
        lambda: None,
        tracking=(lambda: tracking) if tracking else None,
        quiz_agent=lambda: agent or UnconfiguredQuizAgent(),
        quiz_workers=(lambda: workers) if workers else None,
    )
    app.dependency_overrides[get_session] = session
    register_error_handlers(app)
    for routes in (lesson_router, router, public_router, creator_router, video_router):
        app.include_router(routes)
    return app


def create_planned_lesson(client, engine, published=True):
    response = client.post(
        "/api/v1/lessons",
        json={
            "title": "Assignment",
            "description": "Learn variable assignment",
            "minutes": 1,
            "style": {"visualStyleId": "flat-vector-science"},
        },
    )
    assert response.status_code == 201, response.text
    identifier = LessonId(response.json()["id"])
    with Session(engine) as session:
        lessons = SqlAlchemyStandaloneLessons(session)
        lesson = lessons.require_by_id(identifier)
        lesson = replace(
            lesson,
            approved=True,
            content=replace(
                lesson.content,
                plan=lesson_plan(lesson.brief()),
                video_url="https://example.com/lesson.mp4" if published else None,
            ),
        )
        lessons.save(lesson)
        session.commit()
    return str(identifier)
