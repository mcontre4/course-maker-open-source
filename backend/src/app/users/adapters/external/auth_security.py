"""Cryptographic implementations; secrets never appear in logs or browser storage."""

import hashlib
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.users.application.auth_errors import AuthenticationUnavailableError


class ArgonPasswords:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
        self._dummy = self._hasher.hash(secrets.token_urlsafe(32))
        self._slots = BoundedSemaphore(4)

    @contextmanager
    def _capacity(self) -> Iterator[None]:
        # Bound Argon2 memory use across simultaneous requests in this process.
        if not self._slots.acquire(blocking=False):
            raise AuthenticationUnavailableError()
        try:
            yield
        finally:
            self._slots.release()

    def hash(self, password: str) -> str:
        with self._capacity():
            return self._hasher.hash(password)

    def verify(self, password: str, encoded: str | None) -> bool:
        with self._capacity():
            try:
                valid = self._hasher.verify(encoded or self._dummy, password)
                return bool(valid and encoded)
            except (VerificationError, InvalidHashError):
                return False


class SecureTokens:
    def new(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
