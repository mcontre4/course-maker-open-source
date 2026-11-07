"""SQLAlchemy implementation of the user repository port."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.users.adapters.persistence.models import UserRecord
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.user import User
from app.users.domain.user_id import UserId


class SqlAlchemyUserRepository:
    """Translate between user aggregates and SQLAlchemy records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UserId) -> User | None:
        record = self._session.get(UserRecord, str(user_id))
        return self._to_domain(record) if record is not None else None

    def get_by_email(self, email: str) -> User | None:
        statement = select(UserRecord).where(UserRecord.email == email)
        record = self._session.scalar(statement)
        return self._to_domain(record) if record is not None else None

    def add(self, user: User) -> None:
        self._session.add(
            UserRecord(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
            )
        )

        try:
            self._session.flush()
        except IntegrityError as exc:
            if self._is_duplicate_email(exc):
                raise EmailAlreadyRegisteredError(user.email) from exc
            raise

    @staticmethod
    def _is_duplicate_email(error: IntegrityError) -> bool:
        original = error.orig
        if getattr(original, "sqlstate", None) == "23505":
            return bool(
                getattr(getattr(original, "diag", None), "constraint_name", None)
                == "ix_users_email"
            )
        return getattr(original, "args", (None,))[0] == 1062 and "ix_users_email" in str(original)

    @staticmethod
    def _to_domain(record: UserRecord) -> User:
        return User(
            id=UserId(record.id),
            email=record.email,
            first_name=record.first_name,
            last_name=record.last_name,
        )
