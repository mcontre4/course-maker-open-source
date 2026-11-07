from pathlib import Path
from runpy import run_path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from app.courses.adapters.persistence.creators import CreatorRecord
from app.courses.adapters.persistence.models import CourseRecord
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord
from app.shared.infrastructure.database import Base


@pytest.fixture(scope="module")
def creator_database():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url())
        Base.metadata.create_all(
            engine,
            tables=[
                CourseRecord.__table__,
                StandaloneLessonRecord.__table__,
            ],
        )
        migration = run_path(
            str(Path(__file__).parents[3] / "migrations/versions/0005_creator_profiles.py")
        )
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
        yield engine
        engine.dispose()


@pytest.fixture
def creator_sessions(creator_database):
    with creator_database.begin() as connection:
        for table in [
            CreatorRecord.__table__,
            CourseRecord.__table__,
            StandaloneLessonRecord.__table__,
        ]:
            connection.execute(table.delete())
    return sessionmaker(creator_database, expire_on_commit=False)
