import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_flow_round_trip_updates_copies_and_legacy_rows(guide_client, guide_database):
    payload = {
        "title": "Atoms",
        "description": "Teach atoms",
        "minutes": 1,
        "style": {"visualStyleId": "flat-vector-science"},
        "flow": "automatic",
    }
    created = guide_client.post("/api/v1/lessons", json=payload)
    assert created.status_code == 201, created.text
    lesson = created.json()
    path = "/api/v1/lessons/" + lesson["id"]
    assert lesson["flow"] == "automatic"
    assert guide_client.get(path).json()["flow"] == "automatic"
    assert guide_client.get("/api/v1/lessons").json()["items"][0]["flow"] == "automatic"
    copied = guide_client.post(path + "/copy", json={})
    assert copied.status_code == 201, copied.text
    assert copied.json()["flow"] == "guided"

    # Older callers may update details without sending a flow.
    payload.pop("flow")
    updated = guide_client.put(path, json={**payload, "expectedRevision": lesson["revision"]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["flow"] == "automatic"
    updated = guide_client.put(
        path, json={**payload, "flow": "guided", "expectedRevision": updated.json()["revision"]}
    )
    assert updated.status_code == 200, updated.text
    assert guide_client.get(path).json()["flow"] == "guided"
    assert (
        guide_client.post("/api/v1/lessons", json={**payload, "flow": "invalid"}).status_code == 422
    )
    defaulted = guide_client.post("/api/v1/lessons", json=payload)
    assert defaulted.json()["flow"] == "guided"

    # Existing JSON rows have no flow key; load them through the real HTTP/repository path.
    with guide_database.begin() as connection:
        connection.execute(
            text("UPDATE standalone_lessons SET payload = (payload::jsonb - 'flow')::json")
        )
    assert guide_client.get(path).status_code == 200
    assert guide_client.get(path).json()["flow"] == "guided"
