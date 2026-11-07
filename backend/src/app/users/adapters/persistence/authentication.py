"""SQLAlchemy mappings and the account repository; supports PostgreSQL and MySQL."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Double,
    ForeignKey,
    Integer,
    String,
    Text,
    delete,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.shared.infrastructure.database import Base
from app.users.application.errors import EmailAlreadyRegisteredError
from app.users.domain.authentication import Account, AccountAction, AccountMail, LoginSession
from app.users.domain.user_id import UserId


class AccountRecord(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "password_hash IS NOT NULL OR google_subject IS NOT NULL",
            name="ck_account_auth_method",
        ),
    )
    user_id: Mapped[str] = mapped_column(
        String(41),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LoginSessionRecord(Base):
    __tablename__ = "login_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(41),
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[float] = mapped_column(Double)
    expires_at: Mapped[float] = mapped_column(Double, index=True)
    last_seen_at: Mapped[float] = mapped_column(Double)


class AccountActionRecord(Base):
    __tablename__ = "account_actions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(41),
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[float] = mapped_column(Double, index=True)


class AccountMailRecord(Base):
    __tablename__ = "account_mail_outbox"
    id: Mapped[str] = mapped_column(String(41), primary_key=True)
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[float] = mapped_column(Double, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[float] = mapped_column(Double, default=0)


def _account(record: AccountRecord | None) -> Account | None:
    return (
        None
        if record is None
        else Account(
            UserId(record.user_id),
            record.email,
            record.password_hash,
            record.google_subject,
            record.verified,
        )
    )


class SqlAlchemyAccounts:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> Account | None:
        return _account(
            self._session.scalar(select(AccountRecord).where(AccountRecord.email == email))
        )

    def get_by_google_subject(self, subject: str) -> Account | None:
        return _account(
            self._session.scalar(
                select(AccountRecord)
                .where(AccountRecord.google_subject == subject)
                .with_for_update(),
            )
        )

    def get_by_user_id(self, user_id: UserId) -> Account | None:
        return _account(
            self._session.scalar(
                select(AccountRecord)
                .where(AccountRecord.user_id == str(user_id))
                .execution_options(populate_existing=True)
                .with_for_update(),
            )
        )

    def add(self, account: Account) -> None:
        self._session.add(
            AccountRecord(
                user_id=str(account.user_id),
                email=account.email,
                password_hash=account.password_hash,
                google_subject=account.google_subject,
                verified=account.verified,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            code = getattr(exc.orig, "sqlstate", None)
            if code == "23505" or getattr(exc.orig, "args", (None,))[0] == 1062:
                raise EmailAlreadyRegisteredError() from exc
            raise

    def save(self, account: Account) -> None:
        self._session.execute(
            update(AccountRecord)
            .where(
                AccountRecord.user_id == str(account.user_id),
            )
            .values(password_hash=account.password_hash, verified=account.verified)
        )

    def add_session(self, session: LoginSession) -> None:
        self._session.add(
            LoginSessionRecord(
                digest=session.digest,
                user_id=str(session.user_id),
                created_at=session.created_at,
                expires_at=session.expires_at,
                last_seen_at=session.last_seen_at,
            )
        )

    def get_session(self, digest: str) -> LoginSession | None:
        return self._load_session(digest, current=False)

    def get_session_for_authentication(self, digest: str) -> LoginSession | None:
        return self._load_session(digest, current=True)

    def _load_session(self, digest: str, *, current: bool) -> LoginSession | None:
        query = select(LoginSessionRecord).where(LoginSessionRecord.digest == digest)
        if current:
            # A locking read sees revocation committed after an earlier MySQL snapshot.
            # The account is already locked, preserving account -> session lock order.
            query = query.with_for_update()
        record = self._session.scalar(query.execution_options(populate_existing=True))
        return (
            None
            if record is None
            else LoginSession(
                record.digest,
                UserId(record.user_id),
                record.created_at,
                record.expires_at,
                record.last_seen_at,
            )
        )

    def save_session(self, session: LoginSession) -> None:
        self._session.execute(
            update(LoginSessionRecord)
            .where(
                LoginSessionRecord.digest == session.digest,
            )
            .values(last_seen_at=session.last_seen_at)
        )

    def delete_session(self, digest: str) -> None:
        self._session.execute(delete(LoginSessionRecord).where(LoginSessionRecord.digest == digest))

    def revoke_sessions(self, user_id: UserId) -> None:
        self._session.execute(
            delete(LoginSessionRecord).where(
                LoginSessionRecord.user_id == str(user_id),
            )
        )

    def add_action(self, action: AccountAction) -> None:
        self._session.add(
            AccountActionRecord(
                digest=action.digest,
                user_id=str(action.user_id),
                purpose=action.purpose,
                expires_at=action.expires_at,
            )
        )

    def consume_action(self, digest: str, purpose: str, now: float) -> AccountAction | None:
        candidate = self._session.scalar(
            select(AccountActionRecord.user_id).where(
                AccountActionRecord.digest == digest,
                AccountActionRecord.purpose == purpose,
                AccountActionRecord.expires_at > now,
            )
        )
        if candidate is None:
            return None
        # Keep account -> action -> session lock order consistent with resends and login.
        self._session.scalar(
            select(AccountRecord.user_id)
            .where(
                AccountRecord.user_id == candidate,
            )
            .with_for_update()
        )
        record = self._session.scalar(
            select(AccountActionRecord)
            .where(
                AccountActionRecord.digest == digest,
                AccountActionRecord.purpose == purpose,
                AccountActionRecord.expires_at > now,
            )
            .with_for_update()
        )
        if record is None:
            return None
        result = AccountAction(
            record.digest, UserId(record.user_id), record.purpose, record.expires_at
        )
        self._session.delete(record)
        self._session.flush()
        return result

    def delete_actions(self, user_id: UserId, purpose: str) -> None:
        self._session.execute(
            delete(AccountActionRecord).where(
                AccountActionRecord.user_id == str(user_id),
                AccountActionRecord.purpose == purpose,
            )
        )

    def enqueue_mail(self, mail: AccountMail) -> None:
        self._session.add(
            AccountMailRecord(
                id=mail.id,
                recipient=mail.recipient,
                subject=mail.subject,
                body=mail.body,
                expires_at=mail.expires_at,
            )
        )
