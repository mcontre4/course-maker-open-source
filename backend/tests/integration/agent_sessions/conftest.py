import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from app.courses.composition import build_agent_session_factory


@pytest.fixture(scope="session")
def agent_session_engine():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url(), pool_pre_ping=True)
        config = Config("alembic.ini")
        config.attributes["database_url"] = container.get_connection_url()
        command.upgrade(config, "head")
        yield engine
        engine.dispose()


@pytest.fixture
def session_database(agent_session_engine):
    yield agent_session_engine
    with agent_session_engine.begin() as connection:
        connection.execute(
            text("TRUNCATE agent_sessions, standalone_lessons, outline_versions CASCADE")
        )


@pytest.fixture
def persistent_sessions(session_database):
    return build_agent_session_factory(sessionmaker(session_database, expire_on_commit=False))
