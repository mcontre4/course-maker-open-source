"""User aggregate."""

from dataclasses import dataclass

from app.users.domain.errors import UserError
from app.users.domain.user_id import UserId


@dataclass(frozen=True, slots=True)
class User:
    """A registered application user."""

    id: UserId
    email: str
    first_name: str
    last_name: str

    def __post_init__(self) -> None:
        local, separator, domain = self.email.partition("@")
        if (
            not local
            or not separator
            or not domain
            or "@" in domain
            or len(self.email) > 320
            or any(character.isspace() for character in self.email)
        ):
            raise UserError("Use a valid email address of at most 320 characters")
        for name in (self.first_name, self.last_name):
            if not name.strip() or len(name) > 100:
                raise UserError("Names must contain 1–100 characters")
