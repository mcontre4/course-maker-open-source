"""Production account wiring, disposable infrastructure and a deterministic Google port."""

import argparse
from urllib.parse import parse_qs

import httpx
import uvicorn
from alembic import command
from alembic.config import Config
from fakes.authentication import ScriptedGoogle
from fixtures.account_mail import delivered_account_link, wait_for_mailpit
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer

from app.credits.adapters.stripe import StripePayments
from app.main import create_app
from app.shared.infrastructure.settings import Settings
from app.shared.infrastructure.system_clock import SystemClock


def stripe_checkout(request: httpx.Request) -> httpx.Response:
    data = parse_qs(request.content.decode())
    checkout_id = data["metadata[checkout_id]"][0]
    return httpx.Response(
        200,
        json={
            "id": "cs_test_" + checkout_id,
            "url": "https://checkout.stripe.com/c/pay/" + checkout_id,
            "expires_at": SystemClock().now().timestamp() + 86400,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", action="store_true")
    legacy = parser.parse_args().legacy
    with (
        PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres,
        DockerContainer("redis:7.4-alpine").with_exposed_ports(6379) as redis,
        DockerContainer("axllent/mailpit:v1.27").with_exposed_ports(1025, 8025) as smtp,
        httpx.Client(transport=httpx.MockTransport(stripe_checkout)) as stripe,
    ):
        migration = Config("alembic.ini")
        migration.attributes["database_url"] = postgres.get_connection_url()
        command.upgrade(migration, "head")
        settings = Settings(
            _env_file=None,
            database_url=postgres.get_connection_url(),
            redis_url=f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0",
            api_key="browser-test-service-key-of-sufficient-length",
            auth_public_url="http://127.0.0.1:5182",
            auth_enabled=not legacy,
            smtp_host=smtp.get_container_host_ip(),
            smtp_port=int(smtp.get_exposed_port(1025)),
            smtp_starttls=False,
            google_client_id="test-client",
            google_client_secret="test-secret",
        )
        app = create_app(
            settings,
            google_identity=ScriptedGoogle(),
            payments=StripePayments(
                stripe,
                "sk_test_browser",
                "whsec_browser",
                settings.auth_public_url,
                SystemClock(),
            ),
        )
        inbox_url = f"http://{smtp.get_container_host_ip()}:{smtp.get_exposed_port(8025)}"

        @app.get("/__test/mail")
        def test_mail(email: str, subject: str):
            return {"url": delivered_account_link(inbox_url, email, subject)}

        @app.get("/__test/ready")
        def ready():
            return {"status": "ready"}

        wait_for_mailpit(inbox_url)
        httpx.delete(inbox_url + "/api/v1/messages")
        uvicorn.run(app, host="127.0.0.1", port=5183, access_log=False)


if __name__ == "__main__":
    main()
