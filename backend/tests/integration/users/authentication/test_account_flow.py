import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from fixtures.account_mail import delivered_account_link
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.adapters.persistence.authentication import (
    AccountRecord,
    LoginSessionRecord,
    SqlAlchemyAccounts,
)
from app.users.adapters.persistence.user_repository import SqlAlchemyUserRepository

pytestmark = pytest.mark.integration
PASSWORD = "a unique long passphrase 47!"
EMAIL = "ada@example.com"


def test_expired_session_poll_does_not_overwrite_a_newer_browser_cookie(account_client):
    response = account_client.get(
        "/api/v1/auth/session",
        headers={
            "Cookie": "cm_session=revoked-old-session; cm_csrf=existing-csrf-proof",
        },
    )
    assert response.status_code == 200
    assert response.json()["user"] is None
    assert response.headers.get_list("set-cookie") == []


def post(client, path, body=None):
    return client.post("/api/v1/auth/" + path, json=body or {})


def register(client, inbox_url, email=EMAIL):
    response = post(
        client,
        "signup",
        {"email": email, "password": PASSWORD, "first_name": "Ada", "last_name": "Lovelace"},
    )
    assert response.status_code == 202, response.text
    link = delivered_account_link(inbox_url, email.lower(), "Verify your email")
    token = parse_qs(urlsplit(link).fragment)["token"][0]
    assert post(client, "verify-email", {"token": token}).status_code == 200
    return token


def sign_in(client, email=EMAIL, password=PASSWORD):
    response = post(client, "signin", {"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]


def test_credit_purchase_webhook_usage_and_account_isolation(account_app, account_client):
    _, client, inbox = account_app
    assert client.get("/api/v1/credits").status_code == 401
    assert client.get("/api/v1/credits/packs").status_code == 401
    register(client, inbox)
    sign_in(client)
    assert client.get("/api/v1/credits").json() == {"credits": 0}
    assert len(client.get("/api/v1/credits/packs").json()["packs"]) == 3
    policy = client.get("/api/v1/credits/policy").json()
    assert policy["creditsExpire"] is False
    lesson = {
        "title": "Credit lesson",
        "description": "A lesson about physics",
        "minutes": 3,
        "style": {"visualStyleId": "flat-vector-science"},
    }
    assert client.post("/api/v1/lessons", json=lesson).status_code == 402
    assert client.post("/api/v1/credits/checkout", json={"packId": "unknown"}).status_code == 404
    csrf = client.headers.pop("X-CSRF-Token")
    assert (
        client.post("/api/v1/credits/checkout", json={"packId": "pack_starter"}).status_code == 403
    )
    client.headers["X-CSRF-Token"] = csrf
    response = client.post("/api/v1/credits/checkout", json={"packId": "pack_creator"})
    assert response.status_code == 200, response.text
    checkout_id = response.json()["checkoutId"]
    status_url = f"/api/v1/credits/checkout/{checkout_id}"
    assert client.get(status_url).json() == {"status": "pending", "creditsAdded": 0}
    assert client.get("/api/v1/credits").json()["credits"] == 0
    body = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_" + checkout_id,
                "metadata": {"checkout_id": checkout_id},
                "payment_status": "paid",
                "amount_total": 2000,
                "currency": "usd",
            }
        },
    }
    payload = json.dumps(body).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        b"whsec_local_test", timestamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    assert client.post("/api/v1/credits/webhook", content=payload).status_code == 400
    for _ in range(2):
        webhook = client.post(
            "/api/v1/credits/webhook",
            content=payload,
            headers={
                "Stripe-Signature": f"t={timestamp},v1={digest}",
                "Cookie": "",
                "Origin": "",
                "X-CSRF-Token": "",
            },
        )
        assert webhook.status_code == 200, webhook.text
    for _ in range(2):
        assert client.get(status_url).json() == {"status": "paid", "creditsAdded": 550}
    assert client.get("/api/v1/credits").json()["credits"] == 550
    response = client.post("/api/v1/lessons", json=lesson)
    assert response.status_code == 201, response.text
    created = response.json()
    expected = 550 - policy["costs"]["lesson_create"]
    assert client.get("/api/v1/credits").json()["credits"] == expected
    generated = client.post(
        f"/api/v1/lessons/{created['id']}/plan",
        json={"expectedRevision": created["revision"], "message": "Plan this lesson"},
    )
    assert generated.status_code == 200, generated.text
    expected -= policy["costs"]["lesson_generate"]
    assert client.get("/api/v1/credits").json()["credits"] == expected
    # Failed work restores its reservation and records the compensating refund.
    failed = client.post(
        f"/api/v1/lessons/{created['id']}/plan",
        json={"expectedRevision": created["revision"], "message": "Plan this lesson"},
    )
    assert failed.status_code == 409, failed.text
    assert client.get("/api/v1/credits").json()["credits"] == expected
    page = client.get("/api/v1/credits/transactions?limit=2").json()
    assert len(page["items"]) == 2 and page["nextCursor"]
    assert page["items"][0]["kind"] == "refund"
    assert "createdAt" in page["items"][0]
    assert client.get("/api/v1/credits/transactions?cursor=bad").status_code == 400
    assert client.get("/api/v1/credits/transactions?limit=101").status_code == 422
    post(client, "signout")
    data = client.get("/api/v1/auth/session").json()
    client.headers["X-CSRF-Token"] = data["csrf_token"]
    register(client, inbox, "credits-other@example.com")
    sign_in(client, "credits-other@example.com")
    assert client.get(status_url).status_code == 404
    assert client.get("/api/v1/credits").json() == {"credits": 0}
    assert client.get("/api/v1/credits/transactions").json() == {"items": [], "nextCursor": None}


def test_real_account_email_session_and_signout(account_app, account_client, postgres_engine):
    _, client, inbox = account_app
    token = register(account_client, inbox, "ADA@example.com")
    assert post(client, "verify-email", {"token": token}).status_code == 401
    user = sign_in(client, "ADA@example.com")
    assert user["email"] == EMAIL and user["verified"]
    assert client.get("/api/v1/auth/session").json()["user"] == user
    raw_session = client.cookies["cm_session"]
    with Session(postgres_engine) as session:
        repository = SqlAlchemyAccounts(session)
        account = repository.get_by_email(EMAIL)
        assert account.password_hash.startswith("$argon2id$")
        assert SqlAlchemyUserRepository(session).get_by_id(account.user_id).email == EMAIL
        row = session.scalar(select(LoginSessionRecord))
        assert row.digest != raw_session and len(row.digest) == 64
    assert post(client, "signout").status_code == 204
    assert client.get("/api/v1/auth/session").json()["user"] is None
    client.cookies.set("cm_session", raw_session)
    assert client.get("/api/v1/courses").status_code == 401


def test_csrf_origin_validation_body_limits_and_secret_redaction(account_client):
    client = account_client
    headers = {"X-CSRF-Token": "wrong"}
    assert client.post("/api/v1/auth/signout", headers=headers).status_code == 403
    assert (
        client.post("/api/v1/auth/signout", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.post("/api/v1/auth/signout", headers={"Origin": ""}).status_code == 403
    response = post(client, "signup", {"email": EMAIL, "password": "secret-short"})
    assert response.status_code == 422
    assert "secret-short" not in response.text
    assert "no-store" in response.headers["Cache-Control"]
    assert post(client, "signin", {"email": EMAIL, "password": "x" * 20000}).status_code == 413
    assert (
        client.get(
            "/api/v1/courses",
            headers={"Authorization": "Bearer test-service-key-that-is-private-and-long"},
        ).status_code
        == 401
    )


def test_generic_login_duplicate_signup_and_rate_limit(account_app, account_client):
    _, client, inbox = account_app
    payload = {"email": EMAIL, "password": PASSWORD, "first_name": "Ada", "last_name": "Lovelace"}
    first = post(client, "signup", payload)
    duplicate = post(client, "signup", {**payload, "email": EMAIL.upper()})
    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json()
    missing = post(client, "signin", {"email": "missing@example.com", "password": PASSWORD})
    unverified = post(client, "signin", {"email": EMAIL, "password": PASSWORD})
    assert missing.status_code == unverified.status_code == 401
    assert missing.json() == unverified.json()
    for _ in range(10):
        limited = post(client, "signin", {"email": "missing@example.com", "password": PASSWORD})
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "900"


def test_reset_delivered_by_smtp_revokes_sessions_and_rejects_replay(account_app, account_client):
    _, client, inbox = account_app
    register(client, inbox)
    sign_in(client)
    old_session = client.cookies["cm_session"]
    assert post(client, "forgot-password", {"email": EMAIL}).status_code == 202
    link = delivered_account_link(inbox, EMAIL, "Reset your password")
    token = parse_qs(urlsplit(link).fragment)["token"][0]
    replacement = "a different unique passphrase 93!"
    assert (
        post(client, "reset-password", {"token": token, "password": replacement}).status_code == 200
    )
    assert (
        post(client, "reset-password", {"token": token, "password": replacement}).status_code == 401
    )
    client.cookies.set("cm_session", old_session)
    assert client.get("/api/v1/courses").status_code == 401
    assert post(client, "signin", {"email": EMAIL, "password": PASSWORD}).status_code == 401
    sign_in(client, password=replacement)


def test_google_cookie_binding_replay_and_subject_login(account_app, account_client):
    app, client, _ = account_app
    start = post(client, "google/start")
    assert start.status_code == 200
    state = parse_qs(urlsplit(start.json()["url"]).query)["state"][0]
    callback = "/api/v1/auth/google/callback"
    # Another browser does not possess the HttpOnly flow binding cookie.
    attacker = TestClient(app, base_url="http://localhost:5180")
    try:
        assert (
            attacker.get(
                callback, params={"state": state, "code": "valid-code"}, follow_redirects=False
            )
            .headers["location"]
            .endswith("error=google")
        )
    finally:
        attacker.close()
    result = client.get(
        callback, params={"state": state, "code": "valid-code"}, follow_redirects=False
    )
    assert result.status_code == 303 and result.headers["location"] == "http://localhost:5180/"
    profile = client.get("/api/v1/auth/session").json()["user"]
    assert profile["email"] == "google@example.com" and profile["verified"]
    replay = client.get(
        callback, params={"state": state, "code": "valid-code"}, follow_redirects=False
    )
    assert replay.headers["location"].endswith("error=google")


def test_private_courses_are_isolated_between_accounts(account_app, account_client):
    _, client, inbox = account_app
    register(client, inbox)
    sign_in(client)
    payload = {
        "title": "Private course",
        "description": "For this account only",
        "duration": {"mode": "total", "hours": 1},
        "style": {"visualStyleId": "flat-vector-science"},
    }
    created = client.post("/api/v1/courses", json=payload)
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]
    assert client.get("/api/v1/courses").json()["total"] == 1
    post(client, "signout")
    data = client.get("/api/v1/auth/session").json()
    client.headers["X-CSRF-Token"] = data["csrf_token"]
    register(client, inbox, "other@example.com")
    sign_in(client, "other@example.com")
    assert client.get("/api/v1/courses").json()["total"] == 0
    assert client.get(f"/api/v1/courses/{course_id}").status_code == 404
    assert client.put(f"/api/v1/courses/{course_id}", json=payload).status_code == 404
    assert client.delete(f"/api/v1/courses/{course_id}").status_code == 404
    assert client.post(f"/api/v1/courses/{course_id}/syllabus/generate", json={}).status_code == 404
    assert client.get("/api/v1/published/discovery").status_code == 200


def test_secure_cookie_configuration_and_prefix(account_app, account_client):
    # Exercise the real HTTPS transport config without a second database or provider.
    from dataclasses import replace

    from app.users.adapters.http.authentication import get_auth_config

    app, client, inbox = account_app
    register(client, inbox)
    app.dependency_overrides[get_auth_config] = lambda: replace(
        app.state.auth.http,
        secure=True,
        public_url="https://accounts.example.com",
    )
    secure_client = TestClient(app, base_url="https://accounts.example.com")
    try:
        data = secure_client.get("/api/v1/auth/session").json()
        response = secure_client.post(
            "/api/v1/auth/signin",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"Origin": "https://accounts.example.com", "X-CSRF-Token": data["csrf_token"]},
        )
        assert response.status_code == 200, response.text
        cookie = next(
            c for c in response.headers.get_list("set-cookie") if "__Host-cm_session" in c
        )
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
        assert "Domain=" not in cookie and "Path=/" in cookie
    finally:
        secure_client.close()


def test_real_database_unique_email(account_app, account_client, postgres_engine):
    from sqlalchemy.exc import IntegrityError

    _, client, inbox = account_app
    register(client, inbox)
    with Session(postgres_engine) as session:
        from app.users.adapters.persistence.models import UserRecord

        account = session.scalar(select(AccountRecord))
        session.add(
            UserRecord(
                id="user_00000000-0000-0000-0000-000000000099",
                email="other@example.com",
                first_name="Other",
                last_name="User",
            )
        )
        session.flush()
        session.add(
            AccountRecord(
                user_id="user_00000000-0000-0000-0000-000000000099",
                email=account.email,
                password_hash="encoded",
                verified=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_concurrent_initial_creator_requests_are_idempotent(account_app, account_client):
    from concurrent.futures import ThreadPoolExecutor

    _, client, inbox = account_app
    register(client, inbox)
    user = sign_in(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.get("/api/v1/creators/me"), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert all(response.json()["id"] == user["id"] for response in responses)


def test_concurrent_reset_requests_leave_one_active_link(
    account_app, account_client, postgres_engine
):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import func

    from app.users.adapters.persistence.authentication import AccountActionRecord

    _, client, inbox = account_app
    register(client, inbox)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: post(client, "forgot-password", {"email": EMAIL}),
                range(2),
            )
        )
    assert [response.status_code for response in responses] == [202, 202]
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(AccountActionRecord)) == 1
