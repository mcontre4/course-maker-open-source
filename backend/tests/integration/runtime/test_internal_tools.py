from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fixtures.authenticated_client import authenticate_client
from pydantic import SecretStr
from sqlalchemy.orm import sessionmaker

from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.domain.spend import GenerationStep, ModelCharge
from app.main import create_app

pytestmark = pytest.mark.integration
INTERNAL_KEY = "internal-integration-key-32-characters"


def test_internal_lookup_crosses_ownership_but_requires_its_own_key(api, clean_mysql):
    lesson = api.post(
        "/api/v1/lessons",
        json={
            "title": "Internal diagnostics fixture",
            "description": "Inspect an existing lesson",
            "minutes": 1,
            "style": {"visualStyleId": "flat-vector-science"},
        },
    ).json()
    lesson_id = lesson["id"]
    ledger = SqlSpendRepository(sessionmaker(clean_mysql))
    ledger.save(
        ModelCharge(
            "charge_inspect",
            None,
            lesson_id,
            "lesson",
            "openrouter",
            "fixture",
            usd=Decimal("0.125"),
        )
    )
    ledger.save_step(GenerationStep("step_inspect", None, lesson_id, "lesson", 100, 140))
    path = f"/api/v1/internal/lessons/{lesson_id}"
    assert api.get(path).status_code == 403
    assert api.post(path + "/refresh").status_code == 403
    assert api.get(path, headers={"X-Internal-Tools-Key": "invalid"}).status_code == 403
    api.cookies.clear()
    authenticate_client(api, "user_00000000-0000-0000-0000-000000000002")
    assert api.get(f"/api/v1/lessons/{lesson_id}").status_code == 404
    headers = {"X-Internal-Tools-Key": INTERNAL_KEY}
    response = api.get(path, headers=headers)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["Cache-Control"]
    result = response.json()
    assert result["title"] == "Internal diagnostics fixture"
    assert result["generationSeconds"] == 40
    assert result["generationActive"] is False
    assert Decimal(result["spend"]["total"]["knownUsd"]) == Decimal("0.125")
    assert api.post(path + "/refresh", headers=headers).json() == result
    assert (
        api.get(
            "/api/v1/internal/lessons/lesson_00000000-0000-0000-0000-000000009999",
            headers=headers,
        ).status_code
        == 404
    )


def test_internal_tools_are_disabled_without_configuration(runtime_settings):
    settings = runtime_settings.model_copy(update={"internal_tools_key": SecretStr("")})
    with TestClient(create_app(settings)) as api:
        path = "/api/v1/internal/lessons/lesson_00000000-0000-0000-0000-000000009999"
        for headers in ({}, {"X-Internal-Tools-Key": INTERNAL_KEY}):
            assert api.get(path, headers=headers).status_code == 404
            assert api.post(path + "/refresh", headers=headers).status_code == 404
        assert not any("/internal/" in path for path in api.get("/openapi.json").json()["paths"])
