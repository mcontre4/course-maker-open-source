from pathlib import Path
from runpy import run_path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from testcontainers.community.postgres import PostgresContainer

from app.courses.adapters.persistence.lesson_interactive import (
    LessonInteractiveRecord,  # noqa: F401
)
from app.courses.adapters.persistence.lesson_quiz import LessonQuizRecord  # noqa: F401
from app.shared.infrastructure.database import Base


@pytest.fixture(scope="session")
def interactive_engine():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url())
        tables = [t for t in Base.metadata.sorted_tables if t.name != "lesson_interactives"]
        Base.metadata.create_all(engine, tables=tables)
        migration = run_path(
            str(Path(__file__).parents[3] / "migrations/versions/0011_lesson_interactives.py")
        )
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def interactive_database(interactive_engine):
    Base.metadata.create_all(interactive_engine)
    with interactive_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    return interactive_engine
