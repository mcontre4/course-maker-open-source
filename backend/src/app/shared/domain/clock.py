"""Clock port — volatile time dependency owned by the inner layer."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide current time without coupling domain/application to ``datetime``."""

    def now(self) -> datetime: ...
