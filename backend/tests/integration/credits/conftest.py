from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fakes.authentication import MutableAuthClock
from fakes.credits import ScriptedPayments
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def credits_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        url = postgres.get_connection_url()
        config = Config("alembic.ini")
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        engine = create_engine(url, pool_pre_ping=True)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def clean_credits(credits_engine):
    with credits_engine.begin() as connection:
        connection.execute(text("TRUNCATE credit_transactions, credit_checkouts, credit_accounts"))


@pytest.fixture
def clock():
    return MutableAuthClock()


@pytest.fixture
def payments():
    return ScriptedPayments()
