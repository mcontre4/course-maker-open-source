from typing import Protocol


class Catalog(Protocol):
    def topics(self) -> tuple[str, ...]: ...
