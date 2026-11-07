"""Production-composed integration tests for the create-user use case."""

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator
from app.users.adapters.postgres.user_repository import PostgresUserRepository
from app.users.application.create_user import CreateUserRequest
from app.users.composition import build_create_user

pytestmark = pytest.mark.integration


def test_create_user_uses_injected_postgres_dependencies_with_one_session(
    postgres_engine: Engine,
    clean_postgres_database: None,
) -> None:
    with Session(postgres_engine) as session:
        create_user = build_create_user(
            users=PostgresUserRepository(session),
            unit_of_work=SqlAlchemyUnitOfWork(session),
            id_generator=UuidIdGenerator(),
        )
        response = create_user.execute(
            CreateUserRequest(email="ada@example.com", first_name="Ada", last_name="Lovelace")
        )

    with Session(postgres_engine) as session:
        stored_user = PostgresUserRepository(session).get_by_id(response.id)

    assert stored_user is not None
    assert stored_user.email == response.email
    assert stored_user.id == response.id
