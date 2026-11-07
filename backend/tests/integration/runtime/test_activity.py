from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from redis import Redis

from app.courses.adapters.http.activity import (
    ERROR_HEADER,
    HEADER,
    RequestActivity,
    get_activity,
    track_activity,
)
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.ports.speech import SpeechUnavailable

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "failure, expected_error",
    [
        (HTTPException(503, "private provider response"), "The previous step failed."),
        (
            SpeechUnavailable("ElevenLabs speech request failed (HTTP 429)"),
            "ElevenLabs speech request failed (HTTP 429)",
        ),
    ],
)
def test_shared_activity_blocks_duplicates_and_clears_on_success_and_failure(
    redis_server, failure, expected_error, caplog
):
    redis = Redis.from_url(
        f"redis://{redis_server.get_container_host_ip()}:{redis_server.get_exposed_port(6379)}/0",
        decode_responses=True,
    )
    activity = RequestActivity(redis)
    app = FastAPI()
    register_error_handlers(app)
    app.dependency_overrides[get_activity] = lambda: activity
    entered, finish = Event(), Event()
    fail = False

    @app.post("/api/v1/lessons/lesson_test/plan", dependencies=[Depends(track_activity)])
    def plan():
        entered.set()
        assert finish.wait(10)
        if fail:
            raise failure
        return {"saved": True}

    @app.get("/api/v1/lessons/lesson_test", dependencies=[Depends(track_activity)])
    def read():
        return {"id": "lesson_test"}

    try:
        with TestClient(app) as client, ThreadPoolExecutor() as executor:
            for failing in (False, True):
                fail = failing
                entered.clear()
                finish.clear()
                future = executor.submit(client.post, "/api/v1/lessons/lesson_test/plan")
                assert entered.wait(5)
                # A fresh page/client sees activity held by the other request.
                restored = client.get("/api/v1/lessons/lesson_test")
                assert restored.headers[HEADER] == "plan"
                assert restored.headers["Cache-Control"] == "no-store"
                duplicate = client.post("/api/v1/lessons/lesson_test/plan")
                assert duplicate.status_code == 409
                assert "In Progress" in duplicate.json()["detail"]
                finish.set()
                assert future.result().status_code == (503 if failing else 200)
                restored = client.get("/api/v1/lessons/lesson_test")
                assert restored.headers[HEADER] == ""
                assert bool(restored.headers[ERROR_HEADER]) is failing
                if failing:
                    assert expected_error in restored.headers[ERROR_HEADER]
                    assert "private provider response" not in restored.headers[ERROR_HEADER]
                    assert "private provider response" not in caplog.text
    finally:
        finish.set()
        redis.delete(
            "generation-activity:lessons:lesson_test",
            "generation-activity:lessons:lesson_test:error",
        )
        redis.close()


def test_lease_renewal_and_cleanup_never_touch_another_request(redis_server):
    redis = Redis.from_url(
        f"redis://{redis_server.get_container_host_ip()}:{redis_server.get_exposed_port(6379)}/0",
        decode_responses=True,
    )
    activity = RequestActivity(redis)
    key = "generation-activity:lessons:lease_test"
    try:
        old = activity.start(key, "video")
        assert redis.ttl(key) > 0
        redis.expire(key, 10)
        activity.renew(key, old)
        assert redis.ttl(key) > 10
        redis.delete(key)  # Simulate expiration after a worker exits.
        new = activity.start(key, "plan")
        activity.finish(key, old)
        activity.renew(key, old)
        activity.failed(key, old)
        assert activity.read(key) == "plan"
        assert activity.error(key) == ""
        activity.failed(key, new)
        assert "previous step failed" in activity.error(key)
        activity.finish(key, new)
        assert activity.read(key) == ""
        next_token = activity.start(key, "thumbnail")
        assert activity.error(key) == ""
        activity.finish(key, next_token)
    finally:
        redis.delete(key, key + ":error")
        redis.close()


def test_cancellation_fences_only_its_original_worker(redis_server):
    redis = Redis.from_url(
        f"redis://{redis_server.get_container_host_ip()}:{redis_server.get_exposed_port(6379)}/0",
        decode_responses=True,
    )
    activity = RequestActivity(redis)
    key = "generation-activity:lessons:cancel_fencing"
    try:
        first = activity.start(key, "script/generate")
        activity.check(key, first)
        assert activity.cancel(key)
        assert activity.read(key) == "cancelling/script/generate"
        with pytest.raises(HTTPException) as cancelled:
            activity.check(key, first)
        assert cancelled.value.status_code == 409
        activity.finish(key, first)
        assert not activity.cancel(key)
        second = activity.start(key, "video")
        activity.check(key, second)
        with pytest.raises(HTTPException) as stale:
            activity.check(key, first)
        assert stale.value.status_code == 409
        activity.finish(key, first)
        assert activity.read(key) == "video"
    finally:
        redis.delete(key, key + ":cancel", key + ":error")
        redis.close()


@pytest.mark.parametrize("action", ["cancel", "check"])
def test_cancellation_coordination_outage_returns_retryable_error(action):
    with Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1, socket_timeout=0.1) as redis:
        activity = RequestActivity(redis)
        with pytest.raises(HTTPException) as unavailable:
            if action == "cancel":
                activity.cancel("unavailable")
            else:
                activity.check("unavailable", "token")
        assert unavailable.value.status_code == 503
