"""An API using a stale schema must fail before accepting paid generation work."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("missing", ["agent_sessions", "agent_sessions.history_json"])
def test_startup_rejects_missing_persistence_schema(runtime_settings, clean_mysql, missing):
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.attributes["database_url"] = clean_mysql.url.render_as_string(hide_password=False)
    try:
        if missing == "agent_sessions":
            command.downgrade(config, "0012")
        else:
            with clean_mysql.begin() as connection:
                connection.execute(text("ALTER TABLE agent_sessions DROP COLUMN history_json"))
        with pytest.raises(RuntimeError, match="Database schema is out of date") as failure:
            with TestClient(create_app(runtime_settings)):
                pytest.fail("The API accepted requests with an outdated schema")
        assert missing in str(failure.value)
        assert "alembic upgrade head" in str(failure.value)
    finally:
        # Restore the disposable database even when the startup assertion fails.
        if missing != "agent_sessions":
            command.downgrade(config, "0012")
        command.upgrade(config, "head")
    with TestClient(create_app(runtime_settings)) as client:
        assert client.get("/health/live").status_code == 200
