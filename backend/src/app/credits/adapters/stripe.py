import hashlib
import hmac
import json
from urllib.parse import urlsplit

import httpx

from app.credits.domain.models import Checkout, CreditPack, PaymentEvent, PaymentSession
from app.credits.ports.payments import InvalidPaymentEvent, PaymentsUnavailable
from app.shared.domain.clock import Clock


class StripePayments:
    """Hosted Checkout via Stripe's REST API; verify signatures against the raw body."""

    def __init__(
        self, client: httpx.Client, api_key: str, webhook_secret: str, public_url: str, clock: Clock
    ) -> None:
        self._client, self._key, self._secret = client, api_key, webhook_secret
        self._public_url, self._clock = public_url, clock

    def create_session(self, checkout: Checkout, pack: CreditPack) -> PaymentSession:
        if not self._key or not self._secret:
            raise PaymentsUnavailable("Credit checkout is not configured")
        try:
            response = self._client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Idempotency-Key": str(checkout.id),
                    "Stripe-Version": "2026-10-28.endive",
                },
                data={
                    "mode": "payment",
                    "adaptive_pricing[enabled]": "false",
                    "client_reference_id": str(checkout.id),
                    "metadata[checkout_id]": str(checkout.id),
                    "line_items[0][price_data][currency]": checkout.currency.lower(),
                    "line_items[0][price_data][unit_amount]": str(checkout.price_cents),
                    "line_items[0][price_data][product_data][name]": f"{pack.name} credits",
                    "line_items[0][quantity]": "1",
                    "success_url": (
                        f"{self._public_url}/credits?checkout=success&checkout_id={checkout.id}"
                    ),
                    "cancel_url": f"{self._public_url}/credits?checkout=cancelled",
                },
            )
            response.raise_for_status()
            body = response.json()
            identifier, url, expires = body["id"], body["url"], body["expires_at"]
            if (
                not isinstance(identifier, str)
                or not identifier.startswith("cs_")
                or not isinstance(url, str)
                or urlsplit(url).scheme != "https"
                or urlsplit(url).hostname != "checkout.stripe.com"
                or not isinstance(expires, (int, float))
            ):
                raise ValueError("Invalid Stripe checkout response")
            return PaymentSession(identifier, url, float(expires))
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
            raise PaymentsUnavailable("Payment provider unavailable. Please try again.") from error

    def verify_event(self, payload: bytes, signature: str) -> PaymentEvent | None:
        if not self._secret:
            raise PaymentsUnavailable("Credit checkout is not configured")
        try:
            parts = [part.split("=", 1) for part in signature.split(",")]
            timestamp = next(value for key, value in parts if key == "t")
            if abs(self._clock.now().timestamp() - int(timestamp)) > 300:
                raise ValueError("Stale webhook")
            expected = hmac.new(
                self._secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256
            ).hexdigest()
            if not any(
                key == "v1" and hmac.compare_digest(value, expected) for key, value in parts
            ):
                raise ValueError("Invalid signature")
            body = json.loads(payload)
            event_type = body["type"]
            if event_type not in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
                "checkout.session.async_payment_failed",
                "checkout.session.expired",
            }:
                return None
            session = body["data"]["object"]
            checkout_id = session.get("metadata", {}).get("checkout_id")
            if not checkout_id:
                return None
            status = "pending"
            if event_type == "checkout.session.expired":
                status = "expired"
            elif event_type == "checkout.session.async_payment_failed":
                status = "failed"
            elif session.get("payment_status") == "paid":
                status = "paid"
            identifier, amount, currency = (
                session["id"],
                session["amount_total"],
                session["currency"],
            )
            if (
                not isinstance(checkout_id, str)
                or not isinstance(identifier, str)
                or not isinstance(amount, int)
                or not isinstance(currency, str)
            ):
                raise ValueError("Malformed Stripe event")
            from typing import cast

            from app.credits.domain.models import CheckoutStatus

            return PaymentEvent(
                checkout_id, identifier, cast(CheckoutStatus, status), amount, currency
            )
        except (ValueError, TypeError, KeyError, StopIteration, AttributeError) as error:
            raise InvalidPaymentEvent("Invalid Stripe webhook") from error
