"""Infrastructure adapter for the ``Clock`` port."""

from datetime import UTC, datetime


class SystemClock:
    """Provide wall-clock time from the system."""

    def now(self) -> datetime:
        return datetime.now(UTC)
