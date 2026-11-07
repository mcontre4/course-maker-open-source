from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.credits.adapters.persistence import SqlAlchemyCredits
from app.credits.application.grants import GrantCredits, GrantCreditsRequest
from app.credits.application.services import (
    CreateCheckout,
    CreateCheckoutRequest,
    ProcessWebhook,
    WebhookRequest,
)
from app.credits.application.spending import RefundRequest, RefundUsage, SpendCredits, SpendRequest
from app.credits.composition import ScopedCreditBilling
from app.credits.domain.models import CreditAccount, PaymentEvent
from app.shared.application.credit_billing import ChargeRequest
from app.shared.domain.credits import InsufficientCredits
from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator

pytestmark = pytest.mark.integration
OWNER = "user_00000000-0000-0000-0000-000000000001"


def test_concurrent_duplicate_webhooks_fulfill_exactly_once(
    credits_engine,
    clean_credits,
    payments,
    clock,
):
    with Session(credits_engine) as session:
        result = CreateCheckout(
            SqlAlchemyCredits(session),
            SqlAlchemyUnitOfWork(session),
            payments,
            UuidIdGenerator(),
            clock,
        ).execute(CreateCheckoutRequest(OWNER, "pack_creator"))
    payments.event = PaymentEvent(result.checkout_id, "cs_test_1", "paid", 2000, "usd")

    def deliver(_):
        with Session(credits_engine) as session:
            return ProcessWebhook(
                SqlAlchemyCredits(session),
                SqlAlchemyUnitOfWork(session),
                payments,
                UuidIdGenerator(),
                clock,
            ).execute(WebhookRequest(b"event", "signature"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(result.received for result in pool.map(deliver, range(16)))
    with Session(credits_engine) as session:
        repository = SqlAlchemyCredits(session)
        assert repository.get_account(OWNER).credits == 550
        assert len(repository.list_transactions(OWNER, 100, None)) == 1
        assert repository.get_checkout(result.checkout_id).status == "paid"


def test_concurrent_spending_cannot_overdraw_and_refunds_are_idempotent(
    credits_engine,
    clean_credits,
    clock,
):
    with Session(credits_engine) as session:
        repository = SqlAlchemyCredits(session)
        repository.lock_account(OWNER)
        repository.save_account(CreditAccount(OWNER, 10))
        session.commit()

    def spend(_):
        with Session(credits_engine) as session:
            try:
                return (
                    SpendCredits(
                        SqlAlchemyCredits(session),
                        SqlAlchemyUnitOfWork(session),
                        clock,
                        UuidIdGenerator(),
                    )
                    .execute(SpendRequest(OWNER, "lesson_generate", 7))
                    .receipt
                )
            except InsufficientCredits:
                return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = [r for r in pool.map(spend, range(4)) if r]
    assert len(receipts) == 1

    def refund(_):
        with Session(credits_engine) as session:
            return (
                RefundUsage(
                    SqlAlchemyCredits(session),
                    SqlAlchemyUnitOfWork(session),
                    clock,
                    UuidIdGenerator(),
                )
                .execute(RefundRequest(receipts[0]))
                .refunded
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(refund, range(4))) == 1
    with Session(credits_engine) as session:
        repository = SqlAlchemyCredits(session)
        assert repository.get_account(OWNER).credits == 10
        assert sorted(t.kind for t in repository.list_transactions(OWNER, 100, None)) == [
            "refund",
            "usage",
        ]


def test_lazily_created_account_and_database_constraint(credits_engine, clean_credits):
    billing = ScopedCreditBilling(sessionmaker(credits_engine), {"lesson_create": 1})
    with pytest.raises(InsufficientCredits):
        billing.charge(ChargeRequest(OWNER, "lesson_create"))
    with Session(credits_engine) as session:
        assert SqlAlchemyCredits(session).get_account(OWNER).credits == 0
        with pytest.raises(IntegrityError):
            session.execute(
                text("INSERT INTO credit_accounts VALUES (:owner, -1)"), {"owner": OWNER}
            )
            session.commit()


def test_migration_installs_ledger_constraints_and_index(credits_engine):
    schema = inspect(credits_engine)
    assert {"credit_accounts", "credit_transactions", "credit_checkouts"} <= set(
        schema.get_table_names()
    )
    assert "ix_credit_history" in {i["name"] for i in schema.get_indexes("credit_transactions")}
    assert schema.get_unique_constraints("credit_transactions")


def test_concurrent_million_credit_grants_apply_once(credits_engine, clean_credits, clock):
    def grant(_):
        with Session(credits_engine) as session:
            return (
                GrantCredits(
                    SqlAlchemyCredits(session),
                    SqlAlchemyUnitOfWork(session),
                    clock,
                    UuidIdGenerator(),
                )
                .execute(
                    GrantCreditsRequest(
                        OWNER, 1_000_000, "grant:existing-users:owner", "Existing user grant"
                    )
                )
                .granted
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(grant, range(8))) == 1
    with Session(credits_engine) as session:
        repository = SqlAlchemyCredits(session)
        assert repository.get_account(OWNER).credits == 1_000_000
        assert len(repository.list_transactions(OWNER, 100, None)) == 1
