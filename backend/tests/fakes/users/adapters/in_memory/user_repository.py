"""In-memory implementation of the user repository port for tests."""

from app.users.domain.user import User
from app.users.domain.user_id import UserId


class InMemoryUserRepository:
    """Store user aggregates in memory with the user port's lookup behavior."""

    def __init__(self) -> None:
        self._users_by_id: dict[UserId, User] = {}
        self._users_by_email: dict[str, User] = {}

    def get_by_id(self, user_id: UserId) -> User | None:
        return self._users_by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._users_by_email.get(email)

    def add(self, user: User) -> None:
        self._users_by_id[user.id] = user
        self._users_by_email[user.email] = user
