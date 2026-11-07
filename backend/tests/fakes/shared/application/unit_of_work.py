"""Generic unit-of-work test double."""

from types import TracebackType


class FakeUnitOfWork:
    """Record transaction outcomes without depending on a repository or database."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
