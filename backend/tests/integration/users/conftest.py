"""PostgreSQL fixtures shared by user integration tests."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

from app.shared.infrastructure.database import Base


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    """Provide an isolated PostgreSQL schema for user integration tests."""
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        engine = create_engine(postgres.get_connection_url(), pool_pre_ping=True)
        try:
            Base.metadata.create_all(engine)
            yield engine
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()


@pytest.fixture
def clean_postgres_database(postgres_engine: Engine) -> Iterator[None]:
    """Reset PostgreSQL state after a test that explicitly requests it."""
    yield
    table_names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    if table_names:
        with postgres_engine.begin() as connection:
            connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def postgres_session(
    postgres_engine: Engine, clean_postgres_database: None
) -> Iterator[Session]:
    """Provide a PostgreSQL session with explicit per-test cleanup."""
    with Session(postgres_engine) as session:
        yield session
