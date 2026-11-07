import pytest
from fakes.shared.application.unit_of_work import FakeUnitOfWork
from fakes.shared.domain.fake_id_generator import FakeIdGenerator
from fakes.users.adapters.in_memory.user_repository import InMemoryUserRepository

from app.users.application.create_user import CreateUser, CreateUserRequest
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.user import User
from app.users.domain.user_id import UserId


def test_create_user_persists_a_new_user_and_commits() -> None:
    unit_of_work = FakeUnitOfWork()
    users = InMemoryUserRepository()
    id_generator = FakeIdGenerator()

    response = CreateUser(users, unit_of_work, id_generator).execute(
        CreateUserRequest(
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
        )
    )

    stored = users.get_by_id(response.id)
    assert stored is not None
    assert stored.email == "ada@example.com"
    assert stored.first_name == "Ada"
    assert stored.last_name == "Lovelace"
    assert stored.id == response.id
    assert unit_of_work.committed is True
    assert id_generator.calls == 1


def test_create_user_rejects_an_existing_email_without_committing() -> None:
    unit_of_work = FakeUnitOfWork()
    users = InMemoryUserRepository()
    users.add(
        User(
            id=UserId("user_12345678-1234-5678-1234-567812345678"),
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
        )
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        CreateUser(users, unit_of_work, FakeIdGenerator()).execute(
            CreateUserRequest(
                email="ada@example.com",
                first_name="Another",
                last_name="Ada",
            )
        )

    assert unit_of_work.committed is False
    assert unit_of_work.rolled_back is True
