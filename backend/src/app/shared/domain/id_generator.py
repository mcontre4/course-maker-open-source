"""Identity generation port — volatile UUID dependency owned by the inner layer."""

from typing import Protocol
from uuid import UUID


class IdGenerator(Protocol):
    """Generate unique identifiers without coupling domain/application to ``uuid``."""

    def new_uuid(self) -> UUID: ...
