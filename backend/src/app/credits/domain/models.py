from dataclasses import dataclass, replace
from typing import ClassVar, Literal

from app.shared.domain.credits import InsufficientCredits
from app.shared.domain.prefixed_uuid import PrefixedUuid

CheckoutStatus = Literal["pending", "paid", "failed", "expired"]
TransactionKind = Literal["purchase", "usage", "refund", "bonus", "adjustment"]


@dataclass(frozen=True)
class CheckoutId(PrefixedUuid):
    prefix: ClassVar[str] = "checkout_"


@dataclass(frozen=True)
class TransactionId(PrefixedUuid):
    prefix: ClassVar[str] = "credit_"


@dataclass(frozen=True)
class CreditPack:
    id: str
    name: str
    credits: int
    bonus_credits: int
    price_cents: int
    currency: str = "USD"
    badge: str | None = None

    def __post_init__(self) -> None:
        if self.credits <= 0 or self.bonus_credits < 0 or self.price_cents <= 0:
            raise ValueError("Invalid credit pack")


PACKS = (
    CreditPack("pack_starter", "Starter", 100, 0, 500),
    CreditPack("pack_creator", "Creator", 500, 50, 2000, badge="Most popular"),
    CreditPack("pack_studio", "Studio", 1500, 250, 5000, badge="Best value"),
)


@dataclass(frozen=True)
class CreditAccount:
    owner_id: str
    credits: int = 0

    def __post_init__(self) -> None:
        if self.credits < 0:
            raise InsufficientCredits("Not enough credits. Buy credits to continue.")

    def change(self, credits: int) -> "CreditAccount":
        return replace(self, credits=self.credits + credits)


@dataclass(frozen=True)
class CreditTransaction:
    id: TransactionId
    owner_id: str
    kind: TransactionKind
    credits: int
    description: str
    created_at: float
    reference: str

    def __post_init__(self) -> None:
        if (
            self.kind not in {"purchase", "usage", "refund", "bonus", "adjustment"}
            or self.credits == 0
            or (self.kind == "usage" and self.credits > 0)
            or (self.kind in {"purchase", "refund", "bonus"} and self.credits < 0)
        ):
            raise ValueError("Invalid credit transaction")


@dataclass(frozen=True)
class Checkout:
    id: CheckoutId
    owner_id: str
    pack_id: str
    credits: int
    price_cents: int
    currency: str
    status: CheckoutStatus = "pending"
    provider_id: str | None = None
    expires_at: float | None = None

    def __post_init__(self) -> None:
        if self.credits <= 0 or self.price_cents <= 0:
            raise ValueError("Invalid checkout")

    def transition(self, status: CheckoutStatus) -> "Checkout":
        # Late terminal events must never undo a successfully fulfilled payment.
        if self.status == "paid" or (status == "pending" and self.status != "pending"):
            return self
        return replace(self, status=status)


@dataclass(frozen=True)
class PaymentSession:
    id: str
    url: str
    expires_at: float


@dataclass(frozen=True)
class PaymentEvent:
    checkout_id: str
    provider_id: str
    status: CheckoutStatus
    amount_cents: int
    currency: str
