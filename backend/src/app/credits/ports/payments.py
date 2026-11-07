from typing import Protocol

from app.credits.domain.models import Checkout, CreditPack, PaymentEvent, PaymentSession


class PaymentsUnavailable(Exception):
    pass


class InvalidPaymentEvent(ValueError):
    pass


class Payments(Protocol):
    def create_session(self, checkout: Checkout, pack: CreditPack) -> PaymentSession: ...

    def verify_event(self, payload: bytes, signature: str) -> PaymentEvent | None: ...
