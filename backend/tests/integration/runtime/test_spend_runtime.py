from dataclasses import replace
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.domain.spend import ModelCharge

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def internal_access(api):
    api.headers["X-Internal-Tools-Key"] = "internal-integration-key-32-characters"



def test_spend_survives_reload_accumulates_and_deduplicates(api, clean_mysql, draft_payload):
    course = api.post("/api/v1/courses", json=draft_payload).json()
    course_id = course["id"]
    ledger = SqlSpendRepository(sessionmaker(clean_mysql))
    charge = ModelCharge(
        "charge_test",
        course_id,
        "lesson_test",
        "lesson",
        "openrouter",
        "model",
        usd=Decimal("0.000012345678"),
    )
    ledger.save(charge)
    ledger.save(charge)
    ledger.save(replace(charge, id="charge_update", stage="storyboard", usd=Decimal("0.02")))
    ledger.save(
        replace(charge, id="charge_shared", lesson_id=None, stage="syllabus", usd=Decimal("0.01"))
    )
    ledger.save(
        replace(charge, id="charge_pending", usd=None, provider="elevenlabs", credits=Decimal(25))
    )
    restored = SqlSpendRepository(sessionmaker(clean_mysql)).list_by_course_id(course_id)
    assert len(restored) == 4
    response = api.get(f"/api/v1/courses/{course_id}/spend")
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["Cache-Control"]
    body = response.json()
    assert Decimal(body["total"]["knownUsd"]) == Decimal("0.030012345678")
    assert body["total"]["pendingCalls"] == 1
    assert body["total"]["calls"] == 4
    assert Decimal(body["lessons"][0]["total"]["knownUsd"]) == Decimal("0.020012345678")
    assert Decimal(body["shared"]["knownUsd"]) == Decimal("0.01")
    refreshed = api.post(f"/api/v1/courses/{course_id}/spend/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json() == body
    api.delete(f"/api/v1/courses/{course_id}")
    assert ledger.list_by_course_id(course_id) == ()


def test_spend_requires_authentication_and_course(api):
    missing = "/api/v1/courses/course_00000000-0000-0000-0000-000000000099/spend"
    assert api.get(missing).status_code == 404
    assert api.get(missing, headers={"Cookie": ""}).status_code == 401


def test_delayed_pending_write_preserves_reconciled_billing(api, clean_mysql, draft_payload):
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    ledger = SqlSpendRepository(sessionmaker(clean_mysql))
    pending = ModelCharge("charge_late", course_id, "lesson_test", "speech", "elevenlabs", "v4")
    ledger.save(pending)
    resolved = replace(
        pending,
        usd=Decimal("0.01"),
        credits=Decimal(50),
        estimated=True,
        provider_request_id="speech-request",
        model="returned-model",
        input_tokens=100,
    )
    ledger.save(resolved)
    ledger.save(pending)
    assert ledger.list_by_course_id(course_id) == (resolved,)


def test_standalone_spend_round_trip_and_owner_isolation(api, clean_mysql, draft_payload):
    lesson = api.post(
        "/api/v1/lessons",
        json={
            "style": {"visualStyleId": "flat-vector-science"},
            "title": "Constitution",
            "description": "A quick civics lesson",
            "minutes": 1,
        },
    ).json()
    course = api.post("/api/v1/courses", json=draft_payload).json()
    ledger = SqlSpendRepository(sessionmaker(clean_mysql))
    charge = ModelCharge(
        "charge_standalone", None, lesson["id"], "speech", "elevenlabs", "v4", credits=Decimal(100)
    )
    ledger.save(charge)
    ledger.save(charge)
    assert ledger.list_by_lesson_id(lesson["id"]) == (charge,)
    assert ledger.list_by_course_id(course["id"]) == ()
    path = f"/api/v1/lessons/{lesson['id']}/spend"
    response = api.get(path)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["Cache-Control"]
    assert response.json()["total"]["calls"] == 1
    assert response.json()["total"]["credits"] == "100.000000"
    assert api.post(path + "/refresh").json() == response.json()
    api.cookies.clear()
    from fixtures.authenticated_client import authenticate_client

    authenticate_client(api, "user_00000000-0000-0000-0000-000000000002")
    assert api.get(path).status_code == 404
    assert api.post(path + "/refresh").status_code == 404


@pytest.mark.parametrize(
    ("api", "expected_usd", "expected_pending", "expected_estimated"),
    [(None, "0", 3, 0), (Decimal("0.0002"), "0.0758", 0, 3)],
    indirect=["api"],
)
@pytest.mark.parametrize("standalone", [False, True])
def test_refresh_recovers_recorded_speech_credits_with_account_rate(
    api, clean_mysql, draft_payload, standalone, expected_usd, expected_pending, expected_estimated
):
    if standalone:
        lesson = api.post(
            "/api/v1/lessons",
            json={
                "style": {"visualStyleId": "flat-vector-science"},
                "title": "Narration",
                "description": "Billing recovery",
                "minutes": 1,
            },
        ).json()
        course_id, lesson_id = None, lesson["id"]
        path = f"/api/v1/lessons/{lesson_id}/spend"
    else:
        course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
        lesson_id = "lesson_billing_recovery"
        path = f"/api/v1/courses/{course_id}/spend"

    ledger = SqlSpendRepository(sessionmaker(clean_mysql))
    charges = tuple(
        ModelCharge(
            f"charge_speech_{index}",
            course_id,
            lesson_id,
            "speech",
            "elevenlabs",
            "eleven_v4",
            credits=Decimal(credits),
            provider_request_id=f"speech_{index}",
        )
        for index, credits in enumerate((150, 118, 111))
    )
    for charge in charges:
        ledger.save(charge)

    before = api.get(path)
    assert before.status_code == 200, before.text
    assert before.json()["total"]["pendingCalls"] == 3
    assert Decimal(before.json()["total"]["credits"]) == Decimal(379)

    refreshed = api.post(path + "/refresh")
    assert refreshed.status_code == 200, refreshed.text
    result = refreshed.json()
    total = result["total"]
    assert total["pendingCalls"] == expected_pending
    assert total["estimatedCalls"] == expected_estimated
    assert Decimal(total["knownUsd"]) == Decimal(expected_usd)
    assert total["calls"] == 3
    assert Decimal(total["credits"]) == Decimal(379)

    # Delayed response replay cannot erase recovered costs or add duplicate calls.
    for charge in charges:
        ledger.save(charge)
    assert api.get(path).json() == result
    assert api.post(path + "/refresh").json() == result
