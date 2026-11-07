"""Compatibility mode must keep the old gateway and signed-owner contract."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fakes.credits import ScriptedPayments
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.credits.adapters.persistence import SqlAlchemyCredits
from app.credits.application.grants import GrantCredits, GrantCreditsRequest
from app.credits.domain.models import PaymentEvent
from app.main import create_app
from app.shared.infrastructure.sqlalchemy_unit_of_work import SqlAlchemyUnitOfWork
from app.shared.infrastructure.system_clock import SystemClock
from app.shared.infrastructure.uuid_id_generator import UuidIdGenerator

pytestmark = pytest.mark.integration


def test_legacy_mode_keeps_api_key_and_signed_owner_behavior(runtime_settings, draft_payload):
    settings = runtime_settings.model_copy(update={"auth_enabled": False})
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/auth/config").json() == {"enabled": False}
        assert not hasattr(client.app.state, "auth")
        assert client.get("/api/v1/auth/session").status_code == 404
        assert client.post("/api/v1/auth/signup", json={}).status_code == 404
        assert client.get("/api/v1/credits").status_code == 401
        assert client.get("/api/v1/credits/packs").status_code == 401
        assert (
            client.post("/api/v1/credits/checkout", json={"packId": "pack_starter"}).status_code
            == 401
        )
        assert client.get("/api/v1/courses").status_code == 401
        client.headers["Authorization"] = "Bearer wrong-key"
        assert client.get("/api/v1/lessons").status_code == 401
        client.headers["Authorization"] = "Bearer " + settings.api_key.get_secret_value()
        assert client.get("/api/v1/credits").json() == {"credits": 0}
        assert len(client.get("/api/v1/credits/packs").json()["packs"]) == 3
        assert client.get("/api/v1/credits/transactions").json() == {
            "items": [],
            "nextCursor": None,
        }
        course = client.post("/api/v1/courses", json=draft_payload)
        assert course.status_code == 201
        lesson = client.post(
            "/api/v1/lessons",
            json={
                "title": "Legacy lesson",
                "minutes": 3,
                "style": {"visualStyleId": "flat-vector-science"},
            },
        )
        assert lesson.status_code == 201
        saved = lesson.json()["id"]
        cookies = dict(client.cookies)
        assert cookies
        assert client.get("/api/v1/lessons").json()["items"][0]["id"] == saved
    # A restarted API still resolves the existing signed anonymous cookie.
    with TestClient(create_app(settings)) as reopened:
        reopened.headers["Authorization"] = "Bearer " + settings.api_key.get_secret_value()
        reopened.cookies.update(cookies)
        assert reopened.get("/api/v1/lessons").json()["items"][0]["id"] == saved
        reopened.cookies.clear()
        assert reopened.get("/api/v1/lessons").json()["items"] == []
        # Legacy courses were shared behind the gateway key; keep that listing behavior.
        assert reopened.get("/api/v1/courses").json()["items"][0]["id"] == course.json()["id"]


def test_legacy_credits_use_the_signed_owner_for_grants_checkout_and_history(
    runtime_settings,
    clean_mysql,
):
    settings = runtime_settings.model_copy(update={"auth_enabled": False})
    payments = ScriptedPayments()
    with TestClient(create_app(settings, payments=payments)) as client:
        client.headers["Authorization"] = "Bearer " + settings.api_key.get_secret_value()
        assert client.get("/api/v1/credits").json() == {"credits": 0}
        # The same signed owner is used by existing lessons and by the credit wallet.
        from app.courses.adapters.http.lesson_owner import COOKIE

        owner = client.cookies[COOKIE].rpartition(".")[0]
        with Session(clean_mysql) as session:
            GrantCredits(
                SqlAlchemyCredits(session),
                SqlAlchemyUnitOfWork(session),
                SystemClock(),
                UuidIdGenerator(),
            ).execute(
                GrantCreditsRequest(
                    owner,
                    1_000_000,
                    f"grant:test:{owner}",
                    "Existing user credit grant",
                )
            )
        assert client.get("/api/v1/credits").json() == {"credits": 1_000_000}
        history = client.get("/api/v1/credits/transactions").json()
        assert history["items"][0]["kind"] == "bonus"
        assert history["items"][0]["credits"] == 1_000_000
        assert "createdAt" in history["items"][0]
        assert len(client.get("/api/v1/credits/packs").json()["packs"]) == 3
        created = client.post("/api/v1/credits/checkout", json={"packId": "pack_creator"})
        assert created.status_code == 200, created.text
        checkout = created.json()["checkoutId"]
        path = f"/api/v1/credits/checkout/{checkout}"
        assert client.get(path).json() == {"status": "pending", "creditsAdded": 0}
        payments.event = PaymentEvent(checkout, "cs_test_1", "paid", 2000, "usd")
        assert client.post("/api/v1/credits/webhook", content=b"event").status_code == 200
        assert client.get(path).json() == {"status": "paid", "creditsAdded": 550}
        assert client.get("/api/v1/credits").json() == {"credits": 1_000_550}
        signed_cookie = client.cookies[COOKIE]
        client.cookies.clear()
        assert client.get("/api/v1/credits").json() == {"credits": 0}
        assert client.get("/api/v1/credits/transactions").json()["items"] == []
        assert client.get(path).status_code == 404
        client.cookies.clear()
        client.cookies.set(COOKIE, signed_cookie.rpartition(".")[0] + ".forged")
        assert client.get("/api/v1/credits").json() == {"credits": 0}


def test_legacy_startup_accepts_pre_account_schema_but_enabled_mode_rejects_it(
    runtime_settings, clean_mysql
):
    migration = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    migration.attributes["database_url"] = clean_mysql.url.render_as_string(hide_password=False)
    try:
        command.downgrade(migration, "0013")
        settings = runtime_settings.model_copy(update={"auth_enabled": False})
        with TestClient(create_app(settings)) as client:
            assert client.get("/api/v1/auth/config").json() == {"enabled": False}
        with pytest.raises(RuntimeError, match="Database schema is out of date.*accounts"):
            with TestClient(create_app(runtime_settings)):
                pytest.fail("Enabled accounts require their persistence schema")
    finally:
        command.upgrade(migration, "head")
