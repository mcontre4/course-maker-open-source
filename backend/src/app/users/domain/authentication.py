"""Account and session invariants, independent of transport and persistence."""

from dataclasses import dataclass, replace

from app.users.domain.errors import UserError
from app.users.domain.user_id import UserId


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def validate_password(password: str, common_passwords: frozenset[str] = frozenset()) -> None:
    # Permit passphrases, Unicode and paste; never silently truncate or strip.
    if not 15 <= len(password) <= 128:
        raise UserError("Use a password of 15–128 characters")
    if (
        password.casefold() in common_passwords
        or password.casefold()
        in {
            "passwordpassword",
            "123456789012345",
            "qwertyuiopasdfgh",
            "thisisapassword",
        }
        or len(set(password)) < 5
    ):
        raise UserError("Choose a less common password")


@dataclass(frozen=True, slots=True)
class Account:
    user_id: UserId
    email: str
    password_hash: str | None = None
    google_subject: str | None = None
    verified: bool = False

    def __post_init__(self) -> None:
        if self.email != normalize_email(self.email) or "@" not in self.email:
            raise UserError("Account email must be normalized")
        if not self.password_hash and not self.google_subject:
            raise UserError("An account needs an authentication method")

    def verify(self) -> "Account":
        return replace(self, verified=True)

    def reset_password(self, password_hash: str) -> "Account":
        return replace(self, password_hash=password_hash, verified=True)


@dataclass(frozen=True, slots=True)
class LoginSession:
    digest: str
    user_id: UserId
    created_at: float
    expires_at: float
    last_seen_at: float

    def __post_init__(self) -> None:
        if (
            len(self.digest) != 64
            or any(c not in "0123456789abcdef" for c in self.digest)
            or not 0 < self.created_at <= self.last_seen_at < self.expires_at
        ):
            raise UserError("Invalid session")

    def active(self, now: float, idle_seconds: int) -> bool:
        return self.created_at <= now < self.expires_at and now - self.last_seen_at < idle_seconds

    def touch(self, now: float) -> "LoginSession":
        return replace(self, last_seen_at=now)


@dataclass(frozen=True, slots=True)
class AccountAction:
    digest: str
    user_id: UserId
    purpose: str
    expires_at: float

    def __post_init__(self) -> None:
        if (
            len(self.digest) != 64
            or any(c not in "0123456789abcdef" for c in self.digest)
            or self.purpose not in {"verify", "reset"}
            or self.expires_at <= 0
        ):
            raise UserError("Invalid account action")


@dataclass(frozen=True, slots=True)
class AccountMail:
    id: str
    recipient: str
    subject: str
    body: str
    expires_at: float
