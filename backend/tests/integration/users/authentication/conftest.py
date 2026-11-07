from collections.abc import Iterator

import httpx
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fakes.authentication import ScriptedGoogle
from fakes.lesson_agent import SuccessfulLessonAgent
from fastapi.testclient import TestClient
from fixtures.account_mail import wait_for_mailpit
from redis import Redis
from sqlalchemy import Engine, create_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer

from app.credits.adapters.stripe import StripePayments
from app.main import create_app
from app.shared.infrastructure.settings import Settings
from app.shared.infrastructure.system_clock import SystemClock


@pytest.fixture
def account_payments():
    def stripe(request):
        from urllib.parse import parse_qs

        body = parse_qs(request.content.decode())
        identifier = body["metadata[checkout_id]"][0]
        return httpx.Response(
            200,
            json={
                "id": "cs_test_" + identifier,
                "url": "https://checkout.stripe.com/test/" + identifier,
                "expires_at": SystemClock().now().timestamp() + 86400,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(stripe)) as client:
        yield StripePayments(
            client, "sk_test_local", "whsec_local_test", "http://localhost:5180", SystemClock()
        )


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        url = postgres.get_connection_url()
        config = AlembicConfig("alembic.ini")
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        engine = create_engine(url, pool_pre_ping=True)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture(scope="session")
def account_dependencies():
    with DockerContainer("redis:7.4-alpine").with_exposed_ports(6379) as redis_container:
        with DockerContainer("axllent/mailpit:v1.27").with_exposed_ports(1025, 8025) as mail:
            inbox_url = f"http://{mail.get_container_host_ip()}:{mail.get_exposed_port(8025)}"
            wait_for_mailpit(inbox_url)
            yield (
                f"redis://{redis_container.get_container_host_ip()}:"
                f"{redis_container.get_exposed_port(6379)}/0",
                mail.get_container_host_ip(),
                int(mail.get_exposed_port(1025)),
                inbox_url,
            )


@pytest.fixture
def account_app(
    postgres_engine: Engine, clean_postgres_database, account_dependencies, account_payments
):
    redis_url, smtp_host, smtp_port, inbox_url = account_dependencies
    redis = Redis.from_url(redis_url)
    redis.flushdb()
    httpx.delete(inbox_url + "/api/v1/messages")
    settings = Settings(
        _env_file=None,
        database_url=postgres_engine.url.render_as_string(hide_password=False),
        redis_url=redis_url,
        api_key="test-service-key-that-is-private-and-long",
        auth_public_url="http://localhost:5180",
        auth_enabled=True,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_starttls=False,
        google_client_id="test-client",
        google_client_secret="test-secret",
    )
    app = create_app(
        settings,
        google_identity=ScriptedGoogle(),
        payments=account_payments,
        lesson_agent=SuccessfulLessonAgent(),
    )
    with TestClient(app, base_url="http://localhost:5180") as client:
        yield app, client, inbox_url
    redis.close()


@pytest.fixture
def account_client(account_app) -> Iterator[TestClient]:
    app, client, _ = account_app
    data = client.get("/api/v1/auth/session").json()
    client.headers.update({"Origin": "http://localhost:5180", "X-CSRF-Token": data["csrf_token"]})
    yield client
