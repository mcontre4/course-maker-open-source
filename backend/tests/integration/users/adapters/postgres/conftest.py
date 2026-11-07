"""PostgreSQL user-adapter fixtures."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.users.adapters.postgres.user_repository import PostgresUserRepository
from app.users.ports.user_repository import UserRepository


@pytest.fixture
def postgres_user_repository(postgres_session: Session) -> PostgresUserRepository:
    """Provide the user repository bound to this test's PostgreSQL session."""
    return PostgresUserRepository(postgres_session)


@pytest.fixture
def user_repository(postgres_user_repository: PostgresUserRepository) -> UserRepository:
    """Provide this adapter's implementation for shared repository contract tests."""
    return postgres_user_repository


@pytest.fixture
def commit_user_repository(postgres_session: Session) -> Callable[[], None]:
    """Commit the current PostgreSQL transaction for shared contract tests."""
    return postgres_session.commit
