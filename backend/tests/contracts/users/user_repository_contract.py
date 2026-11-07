"""Behavior every user repository implementation must provide."""

from collections.abc import Callable

from app.users.domain.user import User
from app.users.domain.user_id import UserId
from app.users.ports.user_repository import UserRepository


class UserRepositoryContract:
    """Stateless repository-port contract inherited by concrete adapter test suites."""

    def test_can_add_and_retrieve_a_user(
        self,
        user_repository: UserRepository,
        commit_user_repository: Callable[[], None],
    ) -> None:
        user = User(
            id=UserId("user_12345678-1234-5678-1234-567812345678"),
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
        )

        user_repository.add(user)
        commit_user_repository()

        assert user_repository.get_by_id(user.id) == user
        assert user_repository.get_by_email(user.email) == user

    def test_returns_none_for_a_missing_email(self, user_repository: UserRepository) -> None:
        assert user_repository.get_by_email("missing@example.com") is None
