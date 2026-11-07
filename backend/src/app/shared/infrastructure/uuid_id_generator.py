"""Infrastructure adapter for the ``IdGenerator`` port."""

from uuid import UUID, uuid4


class UuidIdGenerator:
    """Generate UUIDs using the system random source."""

    def new_uuid(self) -> UUID:
        return uuid4()
