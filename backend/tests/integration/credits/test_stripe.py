import hashlib
import hmac
import json
from urllib.parse import parse_qs

import httpx
import pytest
from fakes.courses import SequenceIds

from app.credits.adapters.stripe import StripePayments
from app.credits.domain.models import PACKS, Checkout, CheckoutId
from app.credits.ports.payments import InvalidPaymentEvent, PaymentsUnavailable

pytestmark = pytest.mark.integration
SECRET = "whsec_local_test"


def signed(clock, body):
    payload = json.dumps(body).encode()
    timestamp = str(int(clock.now().timestamp()))
    digest = hmac.new(
        SECRET.encode(), timestamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return payload, f"t={timestamp},v1={digest}"


def event(**changes):
    session = {
        "id": "cs_test_1",
        "amount_total": 500,
        "currency": "usd",
        "payment_status": "paid",
        "metadata": {"checkout_id": "checkout_saved"},
    }
    session.update(changes)
    return {"type": "checkout.session.completed", "data": {"object": session}}


def test_checkout_uses_server_price_idempotency_and_fixed_redirects(clock):
    calls = []

    def stripe(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "id": "cs_test_1",
                "url": "https://checkout.stripe.com/test",
                "expires_at": 1900000000,
            },
        )

    checkout = Checkout(CheckoutId.new(SequenceIds()), "owner", "pack_starter", 100, 500, "USD")
    with httpx.Client(transport=httpx.MockTransport(stripe)) as client:
        provider = StripePayments(client, "sk_test_key", SECRET, "http://localhost:5173", clock)
        result = provider.create_session(checkout, PACKS[0])
    assert result.id == "cs_test_1"
    body = parse_qs(calls[0].content.decode())
    assert calls[0].headers["Idempotency-Key"] == str(checkout.id)
    assert body["line_items[0][price_data][unit_amount]"] == ["500"]
    assert body["success_url"] == [
        f"http://localhost:5173/credits?checkout=success&checkout_id={checkout.id}"
    ]
    assert body["cancel_url"] == ["http://localhost:5173/credits?checkout=cancelled"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"id": "cs_1", "url": "http://evil.test", "expires_at": 100}),
    ],
)
def test_provider_errors_are_sanitized(clock, response):
    with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
        provider = StripePayments(client, "sk_test_secret", SECRET, "http://localhost", clock)
        checkout = Checkout(CheckoutId.new(SequenceIds()), "owner", "pack_starter", 100, 500, "USD")
        with pytest.raises(PaymentsUnavailable, match="Payment provider unavailable"):
            provider.create_session(checkout, PACKS[0])


def test_verified_events_cover_delayed_and_terminal_payments(clock):
    with httpx.Client() as client:
        provider = StripePayments(client, "sk_test", SECRET, "http://localhost", clock)
        assert provider.verify_event(*signed(clock, event())).status == "paid"
        assert (
            provider.verify_event(*signed(clock, event(payment_status="unpaid"))).status
            == "pending"
        )
        for kind, status in [
            ("async_payment_succeeded", "paid"),
            ("async_payment_failed", "failed"),
            ("expired", "expired"),
        ]:
            body = event()
            body["type"] = "checkout.session." + kind
            assert provider.verify_event(*signed(clock, body)).status == status
        assert provider.verify_event(*signed(clock, {"type": "unrelated"})) is None
        assert provider.verify_event(*signed(clock, event(metadata={}))) is None


@pytest.mark.parametrize("signature", ["", "t=broken,v1=wrong", "broken", "t=1,v1=bad"])
def test_invalid_signatures_are_rejected(clock, signature):
    with httpx.Client() as client:
        provider = StripePayments(client, "sk_test", SECRET, "http://localhost", clock)
        with pytest.raises(InvalidPaymentEvent):
            provider.verify_event(b"{}", signature)


def test_raw_body_tampering_and_replay_window(clock):
    with httpx.Client() as client:
        provider = StripePayments(client, "sk_test", SECRET, "http://localhost", clock)
        payload, signature = signed(clock, event())
        with pytest.raises(InvalidPaymentEvent):
            provider.verify_event(payload + b" ", signature)
        clock.timestamp += 301
        with pytest.raises(InvalidPaymentEvent):
            provider.verify_event(payload, signature)


def test_disabled_stripe_fails_closed(clock):
    with httpx.Client() as client:
        provider = StripePayments(client, "", "", "http://localhost", clock)
        with pytest.raises(PaymentsUnavailable):
            provider.verify_event(b"{}", "")
