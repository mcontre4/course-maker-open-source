"""Persistence ports used by users application services."""

from typing import Protocol

from app.users.domain.user import User
from app.users.domain.user_id import UserId


class UserRepository(Protocol):
    """Persist and retrieve user aggregates."""

    def get_by_id(self, user_id: UserId) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def add(self, user: User) -> None: ...
