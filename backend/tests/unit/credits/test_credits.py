from dataclasses import replace

import pytest
from fakes.credits import RecordingCreditBilling

from app.credits.application.services import (
    BalanceRequest,
    CheckoutRequest,
    CreateCheckoutRequest,
    CreditsNotFound,
    GetBalance,
    GetCheckout,
    InvalidCreditsRequest,
    ListPacks,
    ListTransactions,
    PacksRequest,
    TransactionsRequest,
    WebhookRequest,
)
from app.credits.application.spending import RefundRequest, RefundUsage, SpendCredits, SpendRequest
from app.credits.domain.models import (
    Checkout,
    CheckoutId,
    CreditAccount,
    CreditPack,
    CreditTransaction,
    PaymentEvent,
    TransactionId,
)
from app.credits.ports.payments import InvalidPaymentEvent, PaymentsUnavailable
from app.shared.application.credit_billing import ChargeRequest, MeteredOwnedUseCase, MeteredUseCase
from app.shared.domain.credits import InsufficientCredits

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"


def purchase(create, payments, webhook, *, pack="pack_creator", status="paid"):
    result = create.execute(CreateCheckoutRequest(OWNER, pack))
    checkout = payments.calls[-1][0]
    payments.event = PaymentEvent(
        result.checkout_id, "cs_test_1", status, checkout.price_cents, "usd"
    )
    webhook.execute(WebhookRequest(b"signed-event", "signature"))
    return result


def test_balance_starts_at_zero_and_packs_match_ui(repository):
    assert GetBalance(repository).execute(BalanceRequest(OWNER)).credits == 0
    packs = ListPacks().execute(PacksRequest()).packs
    assert [(p.id, p.credits, p.bonus_credits, p.price_cents) for p in packs] == [
        ("pack_starter", 100, 0, 500),
        ("pack_creator", 500, 50, 2000),
        ("pack_studio", 1500, 250, 5000),
    ]


def test_checkout_never_grants_credits_on_creation_or_polling(create, repository, clock):
    result = create.execute(CreateCheckoutRequest(OWNER, "pack_creator"))
    checkout = repository.get_checkout(result.checkout_id)
    assert checkout.provider_id == "cs_test_1"
    service = GetCheckout(repository, clock)
    for _ in range(3):
        assert service.execute(CheckoutRequest(OWNER, result.checkout_id)).status == "pending"
    assert repository.get_account(OWNER).credits == 0
    assert not repository.transactions
    with pytest.raises(CreditsNotFound):
        service.execute(CheckoutRequest(OTHER, result.checkout_id))


def test_unknown_pack_and_checkout(create, repository, clock):
    with pytest.raises(CreditsNotFound):
        create.execute(CreateCheckoutRequest(OWNER, "client-invented-pack"))
    with pytest.raises(CreditsNotFound):
        GetCheckout(repository, clock).execute(CheckoutRequest(OWNER, "unknown"))


def test_provider_failure_leaves_reconcilable_checkout(create, payments, repository):
    payments.error = PaymentsUnavailable("offline")
    with pytest.raises(PaymentsUnavailable):
        create.execute(CreateCheckoutRequest(OWNER, "pack_starter"))
    assert len(repository.checkouts) == 1
    assert not repository.transactions


def test_webhook_credits_bonus_once_and_terminal_events_cannot_undo_it(
    create,
    repository,
    payments,
    webhook,
    clock,
):
    result = purchase(create, payments, webhook)
    for status in ("paid", "failed", "expired", "pending"):
        payments.event = replace(payments.event, status=status)
        webhook.execute(WebhookRequest(b"duplicate-or-late", "signature"))
    assert repository.get_account(OWNER).credits == 550
    assert len(repository.transactions) == 1
    assert (
        GetCheckout(repository, clock)
        .execute(CheckoutRequest(OWNER, result.checkout_id))
        .credits_added
        == 550
    )


@pytest.mark.parametrize("status", ["pending", "failed", "expired"])
def test_unpaid_events_do_not_grant_credits(create, payments, webhook, repository, clock, status):
    result = purchase(create, payments, webhook, status=status)
    assert not repository.transactions
    assert (
        GetCheckout(repository, clock).execute(CheckoutRequest(OWNER, result.checkout_id)).status
        == status
    )
    if status == "pending":
        clock.timestamp += 10000000  # Completed but delayed payments can take days.
        assert (
            GetCheckout(repository, clock)
            .execute(CheckoutRequest(OWNER, result.checkout_id))
            .status
            == "pending"
        )
    payments.event = replace(payments.event, status="paid")
    webhook.execute(WebhookRequest(b"late-success", "signature"))
    assert repository.get_account(OWNER).credits == 550


def test_pending_session_expires_without_writing_on_poll(create, repository, clock):
    result = create.execute(CreateCheckoutRequest(OWNER, "pack_starter"))
    clock.timestamp = 1900000001
    assert (
        GetCheckout(repository, clock).execute(CheckoutRequest(OWNER, result.checkout_id)).status
        == "expired"
    )
    assert repository.get_checkout(result.checkout_id).status == "pending"


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": 1},
        {"currency": "eur"},
        {"provider_id": "cs_other"},
    ],
)
def test_webhook_must_match_persisted_purchase(create, payments, webhook, repository, changes):
    result = create.execute(CreateCheckoutRequest(OWNER, "pack_starter"))
    payments.event = replace(
        PaymentEvent(result.checkout_id, "cs_test_1", "paid", 500, "usd"), **changes
    )
    with pytest.raises(InvalidPaymentEvent):
        webhook.execute(WebhookRequest(b"bad-amount", "signature"))
    assert not repository.transactions


def test_irrelevant_or_unknown_webhook_is_acknowledged(webhook, payments):
    assert webhook.execute(WebhookRequest(b"unrelated", "sig")).received
    payments.event = PaymentEvent("unknown", "cs_1", "paid", 500, "usd")
    assert webhook.execute(WebhookRequest(b"unrelated", "sig")).received


def test_spending_and_refunds_are_auditable_and_refund_is_idempotent(
    repository,
    uow,
    clock,
    ids,
):
    repository.save_account(CreditAccount(OWNER, 10))
    service = SpendCredits(repository, uow, clock, ids)
    receipt = service.execute(SpendRequest(OWNER, "lesson_generate", 5)).receipt
    assert repository.get_account(OWNER).credits == 5
    assert repository.get_transaction(receipt).credits == -5
    refund = RefundUsage(repository, uow, clock, ids)
    assert refund.execute(RefundRequest(receipt)).refunded
    assert not refund.execute(RefundRequest(receipt)).refunded
    assert not refund.execute(RefundRequest("unknown")).refunded
    assert repository.get_account(OWNER).credits == 10
    assert len(repository.transactions) == 2


def test_insufficient_funds_never_create_usage(repository, uow, clock, ids):
    with pytest.raises(InsufficientCredits):
        SpendCredits(repository, uow, clock, ids).execute(SpendRequest(OWNER, "lesson_create", 1))
    assert not repository.transactions
    assert uow.rolled_back
    with pytest.raises(ValueError):
        SpendCredits(repository, uow, clock, ids).execute(SpendRequest(OWNER, "lesson_create", 0))


def test_cursor_pagination_is_stable_at_identical_timestamps_and_is_owner_scoped(
    repository,
    clock,
    ids,
):
    for owner in (OWNER, OTHER, OWNER, OWNER):
        identifier = TransactionId.new(ids)
        repository.add_transaction(
            CreditTransaction(
                identifier, owner, "bonus", 1, "Bonus", clock.timestamp, str(identifier)
            )
        )
    service = ListTransactions(repository)
    first = service.execute(TransactionsRequest(OWNER, 2))
    second = service.execute(TransactionsRequest(OWNER, 2, first.next_cursor))
    assert len(first.items) == 2 and len(second.items) == 1
    assert not second.next_cursor
    assert len({t.id for t in first.items + second.items}) == 3


@pytest.mark.parametrize(
    "cursor", ["invalid", "W10=", "bnVsbA==", "WyJOYU4iLCJ4Il0=", "WzEsIHt9XQ=="]
)
def test_invalid_cursors_are_rejected(repository, cursor):
    with pytest.raises(InvalidCreditsRequest):
        ListTransactions(repository).execute(TransactionsRequest(OWNER, cursor=cursor))


def test_invalid_pagination_limit(repository):
    with pytest.raises(InvalidCreditsRequest):
        ListTransactions(repository).execute(TransactionsRequest(OWNER, 0))


def test_metering_reserves_before_work_and_refunds_failures():
    billing = RecordingCreditBilling()

    def success(request):
        assert len(billing.charges) == 1
        return "created"

    assert (
        MeteredUseCase(success, billing, ChargeRequest(OWNER, "lesson_create")).execute(())
        == "created"
    )
    assert not billing.refunds

    def failure(request):
        raise ValueError("generation failed")

    with pytest.raises(ValueError, match="generation failed"):
        MeteredUseCase(failure, billing, ChargeRequest(OWNER, "lesson_generate")).execute(())
    assert billing.refunds == ["receipt"]


def test_metering_never_starts_work_with_insufficient_funds():
    billing = RecordingCreditBilling()
    billing.error = InsufficientCredits("Buy credits")
    calls = []
    with pytest.raises(InsufficientCredits):
        MeteredUseCase(calls.append, billing, ChargeRequest(OWNER, "lesson_create")).execute(())
    assert not calls and not billing.refunds


def test_domain_invariants(ids):
    with pytest.raises(ValueError):
        CreditPack("bad", "Bad", -1, 0, 1)
    with pytest.raises(ValueError):
        CreditTransaction(TransactionId.new(ids), OWNER, "usage", 1, "bad", 0, "bad")
    with pytest.raises(ValueError):
        Checkout(CheckoutId.new(ids), OWNER, "pack", 0, 0, "usd")


@pytest.mark.parametrize("status", ["paid", "pending"])
def test_webhook_can_arrive_before_create_session_returns(
    create,
    payments,
    webhook,
    repository,
    clock,
    status,
):
    def deliver(checkout):
        payments.event = PaymentEvent(str(checkout.id), "cs_test_1", status, 500, "usd")
        webhook.execute(WebhookRequest(b"early-webhook", "signature"))

    payments.on_create = deliver
    result = create.execute(CreateCheckoutRequest(OWNER, "pack_starter"))
    clock.timestamp += 100000000
    checkout = repository.get_checkout(result.checkout_id)
    assert checkout.status == status
    if status == "pending":
        assert checkout.expires_at is None
    else:
        assert repository.get_account(OWNER).credits == 100


def test_late_unpaid_event_does_not_overwrite_failed_payment(create, payments, webhook, repository):
    result = purchase(create, payments, webhook, status="failed")
    payments.event = replace(payments.event, status="pending")
    webhook.execute(WebhookRequest(b"late-unpaid", "signature"))
    assert repository.get_checkout(result.checkout_id).status == "failed"


def test_owned_metering_keeps_owner_in_application_request():
    billing = RecordingCreditBilling()
    service = MeteredOwnedUseCase(lambda request: request.owner_id, billing, "interactive_generate")
    assert service.execute(BalanceRequest(OWNER)) == OWNER
    assert billing.charges == [ChargeRequest(OWNER, "interactive_generate")]
