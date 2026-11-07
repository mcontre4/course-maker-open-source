import pytest
from alembic import command
from alembic.config import Config
from fakes.guide_model import GuideModelScript, scripted_guide
from fastapi.testclient import TestClient
from fixtures.guide_app import build_guide_test_app
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer

from app.courses.adapters.persistence.guide import GuideThreadRecord  # noqa: F401
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord  # noqa: F401

OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def guide_postgres_engine():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url(), pool_pre_ping=True)
        config = Config("alembic.ini")
        config.attributes["database_url"] = container.get_connection_url()
        command.upgrade(config, "head")
        yield engine
        engine.dispose()


@pytest.fixture
def guide_database(guide_postgres_engine):
    yield guide_postgres_engine
    with guide_postgres_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE guide_turns, guide_threads, guide_memories, "
                "outline_versions, standalone_lessons, syllabus_conversations, courses CASCADE"
            )
        )


@pytest.fixture
def model_script():
    return GuideModelScript()


@pytest.fixture
def compacting_guide(model_script):
    return scripted_guide(model_script, threshold=100)


@pytest.fixture
def guide_client_factory(guide_database, model_script):

    def make(owner=OWNER):
        app, specialist = build_guide_test_app(guide_database, model_script, owner)
        client = TestClient(app)
        client.specialist = specialist
        return client

    return make


@pytest.fixture
def guide_client(guide_client_factory):
    with guide_client_factory() as client:
        yield client
