from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep

import pytest

pytestmark = pytest.mark.integration


def create_draft(client):
    response = client.post(
        "/api/v1/lessons",
        json={
            "title": "Atoms",
            "description": "Explain atoms for beginners",
            "minutes": 1,
            "style": {"visualStyleId": "flat-vector-science"},
        },
    )
    assert response.status_code == 201, response.text
    return "/api/v1/lessons/" + response.json()["id"]


@pytest.mark.parametrize("stage", ["storyboard", "script/generate", "video", "automatic"])
def test_cancel_discards_inflight_script_and_preserves_completed_stages(generation_runtime, stage):
    client, _, script, thumbnail = generation_runtime
    # Keep illustrations out of this test's revision/persistence observations.
    thumbnail.gate.block()
    path = create_draft(client)
    planned = client.post(path + "/plan", json={"expectedRevision": 0, "message": "Plan"})
    assert planned.status_code == 200, planned.text
    revision = planned.json()["revision"]
    if stage == "storyboard":
        approved = client.post(path + "/approve", json={"expectedRevision": revision})
        assert approved.status_code == 200, approved.text
        revision = approved.json()["revision"]
    script.gate.block()
    with ThreadPoolExecutor() as executor:
        run = executor.submit(client.post, path + "/" + stage, json={"expectedRevision": revision})
        try:
            assert script.gate.entered.wait(5)
            cancelled = client.post(path + "/generation/cancel")
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json() == {"cancelled": True}
            assert client.get(path).headers["X-Active-Operation"] == "cancelling/" + stage
            # The worker retains its lease until it has acknowledged cancellation.
            assert (
                client.post(path + "/" + stage, json={"expectedRevision": revision}).status_code
                == 409
            )
        finally:
            script.gate.finish.set()
        result = run.result(timeout=5)
        assert result.status_code == 409, result.text
        assert "cancelled" in result.json()["detail"]
    saved = client.get(path)
    assert saved.headers["X-Active-Operation"] == ""
    assert saved.headers["X-Operation-Error"] == ""
    assert saved.json()["content"]["plan"] is not None
    assert saved.json()["content"]["storyboard"] is None
    # A fresh generation is not cancelled by the old token.
    retried = client.post(path + "/storyboard", json={"expectedRevision": saved.json()["revision"]})
    assert retried.status_code == 200, retried.text
    assert retried.json()["content"]["storyboard"] is not None


def test_thumbnail_does_not_block_outline_or_script_and_merges_latest_content(generation_runtime):
    client, lesson, _, thumbnail = generation_runtime
    thumbnail.gate.block()
    lesson.gate.block()
    path = create_draft(client)
    with ThreadPoolExecutor() as executor:
        run = executor.submit(
            client.post, path + "/plan", json={"expectedRevision": 0, "message": "Plan"}
        )
        try:
            assert thumbnail.gate.entered.wait(5)
            assert lesson.gate.entered.wait(5), "Thumbnail must not block the lesson agent"
        finally:
            lesson.gate.finish.set()
        planned = run.result(timeout=5)
        assert planned.status_code == 200, planned.text
    assert not thumbnail.gate.finish.is_set()
    approved = client.post(path + "/approve", json={"expectedRevision": planned.json()["revision"]})
    assert approved.status_code == 200, approved.text
    scripted = client.post(
        path + "/storyboard", json={"expectedRevision": approved.json()["revision"]}
    )
    assert scripted.status_code == 200, scripted.text
    assert not thumbnail.gate.finish.is_set(), (
        "Script can finish while the thumbnail is still running"
    )
    thumbnail.gate.finish.set()
    deadline = monotonic() + 5
    while True:
        saved = client.get(path).json()
        if saved["content"]["image"]:
            break
        assert monotonic() < deadline, "Background illustration should be persisted"
        sleep(0.02)
    assert saved["content"]["image"] == "generated-thumbnail"
    assert saved["content"]["storyboard"] == scripted.json()["content"]["storyboard"]
    assert saved["revision"] == scripted.json()["revision"]


@pytest.mark.parametrize("stage", ["plan", "automatic"])
def test_cancel_outline_does_not_save_a_late_plan(generation_runtime, stage):
    client, lesson, _, thumbnail = generation_runtime
    lesson.gate.block()
    thumbnail.gate.block()
    path = create_draft(client)
    with ThreadPoolExecutor() as executor:
        run = executor.submit(
            client.post, path + "/" + stage, json={"expectedRevision": 0, "message": "Plan"}
        )
        try:
            assert lesson.gate.entered.wait(5)
            # The obsolete owner cookie cannot authenticate a cancellation request.
            denied = client.post(
                path + "/generation/cancel", headers={"Cookie": "course_maker_owner=invalid"}
            )
            assert denied.status_code == 401
            assert client.get(path).headers["X-Active-Operation"] == stage
            assert client.post(path + "/generation/cancel").json() == {"cancelled": True}
        finally:
            lesson.gate.finish.set()
        assert run.result(timeout=5).status_code == 409
    saved = client.get(path).json()
    assert saved["revision"] == 0
    assert saved["content"]["plan"] is None
    assert not saved["approved"]
    assert not generation_runtime[2].calls


def test_course_draft_returns_while_thumbnail_is_running(generation_runtime, draft_payload):
    client, _, _, thumbnail = generation_runtime
    thumbnail.gate.block()
    created = client.post("/api/v1/courses", json=draft_payload)
    assert created.status_code == 201, created.text
    path = "/api/v1/courses/" + created.json()["id"]
    try:
        assert thumbnail.gate.entered.wait(5)
        saved = client.get(path)
        assert saved.headers["X-Active-Operation"] == ""
        assert saved.headers["X-Thumbnail-Operation"] == "thumbnail"
        assert client.post(path + "/thumbnail", json={}).status_code == 409
        # Thumbnail work is independent and is not the target of generation cancellation.
        assert client.post(path + "/generation/cancel").json() == {"cancelled": False}
    finally:
        thumbnail.gate.finish.set()


def test_automatic_failure_is_visible_after_reload_and_releases_lease(generation_runtime):
    from app.courses.ports.lesson_agent import LessonGenerationUnavailable

    client, lesson, _, thumbnail = generation_runtime
    thumbnail.gate.block()
    path = create_draft(client)
    lesson.error = LessonGenerationUnavailable("Provider unavailable")
    failed = client.post(path + "/automatic", json={"expectedRevision": 0})
    assert failed.status_code == 503, failed.text
    saved = client.get(path)
    assert saved.headers["X-Active-Operation"] == ""
    assert saved.headers["X-Operation-Error"]
    assert saved.json()["revision"] == 0
    lesson.error = None
    retried = client.post(path + "/plan", json={"expectedRevision": 0, "message": "Retry"})
    assert retried.status_code == 200, retried.text
    assert client.get(path).headers["X-Operation-Error"] == ""
