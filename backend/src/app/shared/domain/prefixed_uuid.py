"""Domain value-object base for prefixed UUID identifiers."""

from dataclasses import dataclass
from typing import ClassVar, Self
from uuid import UUID

from app.shared.domain.errors import InvalidIdentifierError
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True, slots=True)
class PrefixedUuid:
    """A canonical identifier in a subclass-defined ``<prefix><UUID>`` format."""

    value: str

    prefix: ClassVar[str]

    def __post_init__(self) -> None:
        message = f"ID must use the {self.prefix}<UUID> format."
        if not self.value.startswith(self.prefix):
            raise InvalidIdentifierError(message)

        try:
            canonical_uuid = UUID(self.value.removeprefix(self.prefix))
        except ValueError as error:
            raise InvalidIdentifierError(message) from error

        if self.value != f"{self.prefix}{canonical_uuid}":
            raise InvalidIdentifierError(message)

    @classmethod
    def new(cls, id_generator: IdGenerator) -> Self:
        """Generate an identifier using the subclass's prefix."""
        return cls(f"{cls.prefix}{id_generator.new_uuid()}")

    def __str__(self) -> str:
        return self.value
