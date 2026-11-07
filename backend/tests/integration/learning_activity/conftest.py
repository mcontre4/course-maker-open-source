from pathlib import Path
from runpy import run_path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from app.courses.adapters.persistence.learning_activity import LearningActivityRecord


@pytest.fixture(scope="module")
def activity_database():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url())
        migration = run_path(
            str(Path(__file__).parents[3] / "migrations/versions/0012_learning_activity.py")
        )
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
        yield engine
        engine.dispose()


@pytest.fixture
def activity_sessions(activity_database):
    with activity_database.begin() as connection:
        connection.execute(LearningActivityRecord.__table__.delete())
    return sessionmaker(activity_database, expire_on_commit=False)
