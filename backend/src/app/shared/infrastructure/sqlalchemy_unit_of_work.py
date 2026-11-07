"""SQLAlchemy implementation of the generic transaction boundary."""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session


class SqlAlchemyUnitOfWork:
    """Commit, roll back, and close a single SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is not None or self._session.in_transaction():
            self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
