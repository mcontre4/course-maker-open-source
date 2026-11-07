from pathlib import Path
from runpy import run_path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fakes.lesson_quiz import RecordingQuizAgent
from redis import Redis
from sqlalchemy import create_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from app.courses.adapters.persistence.lesson_quiz import LessonQuizAttemptRecord, LessonQuizRecord
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord
from app.shared.infrastructure.database import Base


@pytest.fixture(scope="session")
def quiz_engine():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url())
        tables = [
            t
            for t in Base.metadata.sorted_tables
            if t.name not in {"lesson_quizzes", "lesson_quiz_attempts"}
        ]
        Base.metadata.create_all(engine, tables=tables)
        migration = run_path(
            str(Path(__file__).parents[3] / "migrations/versions/0010_lesson_quizzes.py")
        )
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def quiz_database(quiz_engine):
    with quiz_engine.begin() as connection:
        for table in (
            LessonQuizAttemptRecord.__table__,
            LessonQuizRecord.__table__,
            StandaloneLessonRecord.__table__,
        ):
            connection.execute(table.delete())
    return quiz_engine


@pytest.fixture(scope="session")
def quiz_redis_service():
    with RedisContainer("redis:7-alpine") as container:
        client = Redis(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(6379)),
            decode_responses=True,
        )
        try:
            yield client
        finally:
            client.close()


@pytest.fixture
def quiz_redis(quiz_redis_service):
    quiz_redis_service.flushdb()
    return quiz_redis_service


@pytest.fixture
def quiz_agent():
    return RecordingQuizAgent()
