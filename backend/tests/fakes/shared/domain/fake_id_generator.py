"""Deterministic IdGenerator test double."""

from uuid import UUID


class FakeIdGenerator:
    """Return pre-configured UUIDs to make identity generation deterministic in tests."""

    def __init__(self, fixed_uuid: UUID | None = None) -> None:
        self._fixed_uuid = fixed_uuid or UUID("12345678-1234-5678-1234-567812345678")
        self.calls = 0

    def new_uuid(self) -> UUID:
        self.calls += 1
        return self._fixed_uuid
