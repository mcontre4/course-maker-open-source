import base64
import json
import math
from dataclasses import dataclass, replace

from app.credits.domain.models import (
    PACKS,
    Checkout,
    CheckoutId,
    CheckoutStatus,
    CreditTransaction,
    TransactionId,
    TransactionKind,
)
from app.credits.ports.payments import InvalidPaymentEvent, Payments
from app.credits.ports.repository import CreditsRepository
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock
from app.shared.domain.id_generator import IdGenerator


class CreditsNotFound(Exception):
    pass


class InvalidCreditsRequest(ValueError):
    pass


@dataclass(frozen=True)
class PacksRequest:
    pass


@dataclass(frozen=True)
class PackResponse:
    id: str
    name: str
    credits: int
    bonus_credits: int
    price_cents: int
    currency: str
    badge: str | None


@dataclass(frozen=True)
class PacksResponse:
    packs: tuple[PackResponse, ...]


class ListPacks:
    def execute(self, request: PacksRequest) -> PacksResponse:
        return PacksResponse(
            tuple(
                PackResponse(
                    p.id, p.name, p.credits, p.bonus_credits, p.price_cents, p.currency, p.badge
                )
                for p in PACKS
            )
        )


@dataclass(frozen=True)
class BalanceRequest:
    owner_id: str


@dataclass(frozen=True)
class BalanceResponse:
    credits: int


class GetBalance:
    def __init__(self, repository: CreditsRepository) -> None:
        self._repository = repository

    def execute(self, request: BalanceRequest) -> BalanceResponse:
        return BalanceResponse(self._repository.get_account(request.owner_id).credits)


@dataclass(frozen=True)
class TransactionsRequest:
    owner_id: str
    limit: int = 20
    cursor: str | None = None


@dataclass(frozen=True)
class TransactionResponse:
    id: str
    kind: TransactionKind
    credits: int
    description: str
    created_at: float


@dataclass(frozen=True)
class TransactionsResponse:
    items: tuple[TransactionResponse, ...]
    next_cursor: str | None


class ListTransactions:
    def __init__(self, repository: CreditsRepository) -> None:
        self._repository = repository

    def execute(self, request: TransactionsRequest) -> TransactionsResponse:
        if not 1 <= request.limit <= 100:
            raise InvalidCreditsRequest("Limit must be between 1 and 100")
        before = None
        if request.cursor:
            try:
                timestamp, identifier = json.loads(
                    base64.b64decode(request.cursor, altchars=b"-_", validate=True)
                )
                if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                    raise ValueError
                if not isinstance(identifier, str):
                    raise ValueError
                before = (float(timestamp), str(TransactionId(identifier)))
            except (ValueError, TypeError, UnicodeError, OverflowError) as error:
                raise InvalidCreditsRequest("Invalid transaction cursor") from error
        rows = self._repository.list_transactions(request.owner_id, request.limit + 1, before)
        page = rows[: request.limit]
        cursor = None
        if len(rows) > request.limit:
            last = page[-1]
            cursor = base64.urlsafe_b64encode(
                json.dumps([last.created_at, str(last.id)]).encode()
            ).decode()
        return TransactionsResponse(
            tuple(
                TransactionResponse(str(t.id), t.kind, t.credits, t.description, t.created_at)
                for t in page
            ),
            cursor,
        )


@dataclass(frozen=True)
class CreateCheckoutRequest:
    owner_id: str
    pack_id: str


@dataclass(frozen=True)
class CreateCheckoutResponse:
    checkout_id: str
    url: str


class CreateCheckout:
    def __init__(
        self,
        repository: CreditsRepository,
        uow: UnitOfWork,
        payments: Payments,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._repository, self._uow, self._payments = repository, uow, payments
        self._ids, self._clock = ids, clock

    def execute(self, request: CreateCheckoutRequest) -> CreateCheckoutResponse:
        pack = next((p for p in PACKS if p.id == request.pack_id), None)
        if pack is None:
            raise CreditsNotFound("Credit pack not found")
        checkout = Checkout(
            CheckoutId.new(self._ids),
            request.owner_id,
            pack.id,
            pack.credits + pack.bonus_credits,
            pack.price_cents,
            pack.currency,
            expires_at=self._clock.now().timestamp() + 86400,
        )
        with self._uow:
            self._repository.add_checkout(checkout)
            self._uow.commit()
        # No transaction may stay open during the provider call.
        session = self._payments.create_session(checkout, pack)
        with self._uow:
            current = self._repository.get_checkout(str(checkout.id), lock=True)
            assert current is not None
            if current.provider_id not in {None, session.id}:
                raise InvalidPaymentEvent("Checkout provider mismatch")
            self._repository.save_checkout(
                replace(
                    current,
                    provider_id=session.id,
                    expires_at=session.expires_at
                    if current.provider_id is None
                    else current.expires_at,
                )
            )
            self._uow.commit()
        return CreateCheckoutResponse(str(checkout.id), session.url)


@dataclass(frozen=True)
class CheckoutRequest:
    owner_id: str
    checkout_id: str


@dataclass(frozen=True)
class CheckoutResponse:
    status: CheckoutStatus
    credits_added: int


class GetCheckout:
    def __init__(self, repository: CreditsRepository, clock: Clock) -> None:
        self._repository, self._clock = repository, clock

    def execute(self, request: CheckoutRequest) -> CheckoutResponse:
        checkout = self._repository.get_checkout(request.checkout_id)
        if checkout is None or checkout.owner_id != request.owner_id:
            raise CreditsNotFound("Checkout not found")
        status = checkout.status
        if status == "pending" and checkout.expires_at is not None:
            if checkout.expires_at <= self._clock.now().timestamp():
                status = "expired"
        return CheckoutResponse(status, checkout.credits if status == "paid" else 0)


@dataclass(frozen=True)
class WebhookRequest:
    payload: bytes
    signature: str


@dataclass(frozen=True)
class WebhookResponse:
    received: bool = True


class ProcessWebhook:
    def __init__(
        self,
        repository: CreditsRepository,
        uow: UnitOfWork,
        payments: Payments,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._repository, self._uow, self._payments = repository, uow, payments
        self._ids, self._clock = ids, clock

    def execute(self, request: WebhookRequest) -> WebhookResponse:
        event = self._payments.verify_event(request.payload, request.signature)
        if event is None:
            return WebhookResponse()
        with self._uow:
            checkout = self._repository.get_checkout(event.checkout_id, lock=True)
            if checkout is None:
                # Other Stripe products may share this endpoint/account.
                return WebhookResponse()
            if (
                checkout.provider_id not in {None, event.provider_id}
                or checkout.price_cents != event.amount_cents
                or checkout.currency.lower() != event.currency.lower()
            ):
                raise InvalidPaymentEvent("Payment does not match checkout")
            if checkout.status == "paid":
                return WebhookResponse()
            updated = replace(checkout.transition(event.status), provider_id=event.provider_id)
            if event.status == "pending" and checkout.status == "pending":
                updated = replace(updated, expires_at=None)
            if event.status == "paid":
                account = self._repository.lock_account(checkout.owner_id)
                self._repository.save_account(account.change(checkout.credits))
                self._repository.add_transaction(
                    CreditTransaction(
                        TransactionId.new(self._ids),
                        checkout.owner_id,
                        "purchase",
                        checkout.credits,
                        f"Credit pack purchase ({checkout.pack_id})",
                        self._clock.now().timestamp(),
                        str(checkout.id),
                    )
                )
            self._repository.save_checkout(updated)
            self._uow.commit()
        return WebhookResponse()
