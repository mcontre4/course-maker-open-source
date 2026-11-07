from collections.abc import Callable
from typing import Self, cast

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.courses.domain.errors import CourseConflict
from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork


class CourseUnitOfWork(SqlAlchemyUnitOfWork):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._check_generation = cast(
            Callable[[], None] | None, session.info.get("check_generation")
        )

    def __enter__(self) -> Self:
        if self._check_generation:
            self._check_generation()
        return super().__enter__()

    def commit(self) -> None:
        if self._check_generation:
            self._check_generation()
        try:
            super().commit()
        except StaleDataError as exc:
            raise CourseConflict("Course changed concurrently; reload and retry") from exc
