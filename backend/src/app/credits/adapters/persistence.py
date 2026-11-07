from typing import cast

from sqlalchemy import CheckConstraint, Double, Index, Integer, String, and_, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.credits.domain.models import (
    Checkout,
    CheckoutId,
    CheckoutStatus,
    CreditAccount,
    CreditTransaction,
    TransactionId,
    TransactionKind,
)
from app.shared.infrastructure.database import Base


class CreditAccountRecord(Base):
    __tablename__ = "credit_accounts"
    __table_args__ = (CheckConstraint("credits >= 0", name="ck_credits_nonnegative"),)
    owner_id: Mapped[str] = mapped_column(String(41), primary_key=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)


class CreditTransactionRecord(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        CheckConstraint("credits <> 0", name="ck_credit_transaction_nonzero"),
        CheckConstraint(
            "(kind = 'usage' AND credits < 0) OR "
            "(kind IN ('purchase', 'refund', 'bonus') AND credits > 0) OR kind = 'adjustment'",
            name="ck_credit_transaction_direction",
        ),
        Index("ix_credit_history", "owner_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(43), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(41), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[float] = mapped_column(Double, nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class CreditCheckoutRecord(Base):
    __tablename__ = "credit_checkouts"
    __table_args__ = (
        CheckConstraint("credits > 0 AND price_cents > 0", name="ck_checkout_positive"),
    )
    id: Mapped[str] = mapped_column(String(45), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(41), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(50), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    expires_at: Mapped[float | None] = mapped_column(Double)


def _transaction(row: CreditTransactionRecord) -> CreditTransaction:
    return CreditTransaction(
        TransactionId(row.id),
        row.owner_id,
        cast(TransactionKind, row.kind),
        row.credits,
        row.description,
        row.created_at,
        row.reference,
    )


class SqlAlchemyCredits:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_account(self, owner_id: str) -> CreditAccount:
        row = self._session.get(CreditAccountRecord, owner_id)
        return CreditAccount(owner_id, row.credits if row else 0)

    def lock_account(self, owner_id: str) -> CreditAccount:
        # Atomic lazy initialization works for existing accounts and simultaneous first requests.
        values = {"owner_id": owner_id, "credits": 0}
        if self._session.get_bind().dialect.name == "postgresql":
            statement = postgres_insert(CreditAccountRecord).values(**values)
            self._session.execute(statement.on_conflict_do_nothing())
        else:
            statement_mysql = mysql_insert(CreditAccountRecord).values(**values)
            self._session.execute(statement_mysql.on_duplicate_key_update(owner_id=owner_id))
        row = self._session.execute(
            select(CreditAccountRecord)
            .where(CreditAccountRecord.owner_id == owner_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        return CreditAccount(row.owner_id, row.credits)

    def save_account(self, account: CreditAccount) -> None:
        self._session.merge(CreditAccountRecord(owner_id=account.owner_id, credits=account.credits))
        self._session.flush()

    def add_transaction(self, transaction: CreditTransaction) -> None:
        self._session.add(
            CreditTransactionRecord(
                id=str(transaction.id),
                owner_id=transaction.owner_id,
                kind=transaction.kind,
                credits=transaction.credits,
                description=transaction.description,
                created_at=transaction.created_at,
                reference=transaction.reference,
            )
        )
        self._session.flush()

    def get_transaction(self, reference: str) -> CreditTransaction | None:
        row = self._session.scalar(
            select(CreditTransactionRecord)
            .where(CreditTransactionRecord.reference == reference)
            .with_for_update()
        )
        return _transaction(row) if row else None

    def list_transactions(
        self, owner_id: str, limit: int, before: tuple[float, str] | None
    ) -> tuple[CreditTransaction, ...]:
        query = select(CreditTransactionRecord).where(CreditTransactionRecord.owner_id == owner_id)
        if before:
            timestamp, identifier = before
            query = query.where(
                or_(
                    CreditTransactionRecord.created_at < timestamp,
                    and_(
                        CreditTransactionRecord.created_at == timestamp,
                        CreditTransactionRecord.id < identifier,
                    ),
                )
            )
        query = query.order_by(
            CreditTransactionRecord.created_at.desc(), CreditTransactionRecord.id.desc()
        ).limit(limit)
        return tuple(_transaction(row) for row in self._session.scalars(query))

    def add_checkout(self, checkout: Checkout) -> None:
        self._session.add(self._checkout_record(checkout))
        self._session.flush()

    def get_checkout(self, checkout_id: str, *, lock: bool = False) -> Checkout | None:
        query = select(CreditCheckoutRecord).where(CreditCheckoutRecord.id == checkout_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self._session.scalar(query)
        return (
            Checkout(
                CheckoutId(row.id),
                row.owner_id,
                row.pack_id,
                row.credits,
                row.price_cents,
                row.currency,
                cast(CheckoutStatus, row.status),
                row.provider_id,
                row.expires_at,
            )
            if row
            else None
        )

    def save_checkout(self, checkout: Checkout) -> None:
        self._session.merge(self._checkout_record(checkout))
        self._session.flush()

    @staticmethod
    def _checkout_record(checkout: Checkout) -> CreditCheckoutRecord:
        return CreditCheckoutRecord(
            id=str(checkout.id),
            owner_id=checkout.owner_id,
            pack_id=checkout.pack_id,
            credits=checkout.credits,
            price_cents=checkout.price_cents,
            currency=checkout.currency,
            status=checkout.status,
            provider_id=checkout.provider_id,
            expires_at=checkout.expires_at,
        )
