"""Shared request coordination; activity outlives the browser that initiated it."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, Response
from redis import Redis
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool

from app.courses.ports.speech import SpeechUnavailable

HEADER = "X-Active-Operation"
ERROR_HEADER = "X-Operation-Error"
THUMBNAIL_HEADER = "X-Thumbnail-Operation"
LEASE_SECONDS = 60
_START = (
    "if redis.call('set', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2]) then "
    "redis.call('del', KEYS[2]); return 1 end return 0"
)
_FAILED = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('set', KEYS[2], ARGV[2], 'EX', 86400) end return nil"
)
_COMPARE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call(ARGV[2], KEYS[1], unpack(ARGV, 3)) end return 0"
)
_CANCEL = (
    "local token = redis.call('get', KEYS[1]); "
    "if not token then return 0 end "
    "redis.call('set', KEYS[2], token, 'EX', 86400); return 1"
)
_CHECK = "return redis.call('get', KEYS[1]) == ARGV[1] and redis.call('get', KEYS[2]) ~= ARGV[1]"


class RequestActivity:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def read(self, key: str) -> str:
        value = self._redis.get(key)
        if not value:
            return ""
        operation = str(value).split(":", 1)[1]
        return "cancelling/" + operation if self._redis.get(key + ":cancel") == value else operation

    def cancel(self, key: str) -> bool:
        try:
            return bool(self._redis.eval(_CANCEL, 2, key, key + ":cancel"))
        except RedisError as exc:
            raise HTTPException(
                503, "Cannot request cancellation. Please try again shortly."
            ) from exc

    def check(self, key: str, token: str) -> None:
        try:
            active = self._redis.eval(_CHECK, 2, key, key + ":cancel", token)
        except RedisError as exc:
            raise HTTPException(
                503, "Cannot verify generation status. Please try again shortly."
            ) from exc
        if not active:
            raise HTTPException(409, "Generation cancelled. Completed stages are saved.")

    def error(self, key: str) -> str:
        return str(self._redis.get(key + ":error") or "")

    def failed(self, key: str, token: str, message: str | None = None) -> None:
        self._redis.eval(
            _FAILED,
            2,
            key,
            key + ":error",
            token,
            message or "The previous step failed. Completed work is saved. Please try again.",
        )

    def start(self, key: str, operation: str, lease_seconds: int = LEASE_SECONDS) -> str:
        token = f"{uuid4()}:{operation}"
        if not self._redis.eval(_START, 2, key, key + ":error", token, lease_seconds):
            raise HTTPException(409, "In Progress: wait for the current step to finish.")
        return token

    def renew(self, key: str, token: str) -> None:
        self._redis.eval(_COMPARE, 1, key, token, "expire", LEASE_SECONDS)

    def finish(self, key: str, token: str) -> None:
        self._redis.eval(_COMPARE, 1, key, token, "del")


def get_activity() -> RequestActivity:
    raise RuntimeError("Request activity is not configured")


async def track_activity(
    request: Request,
    response: Response,
    activity: Annotated[RequestActivity, Depends(get_activity)],
) -> AsyncIterator[None]:
    parts = request.url.path.strip("/").split("/")
    if len(parts) < 4 or parts[:2] != ["api", "v1"] or parts[2] not in {"courses", "lessons"}:
        yield
        return
    key = f"generation-activity:{parts[2]}:{parts[3]}"
    operation = "/".join(parts[4:]) or "update"
    try:
        if request.method == "GET":
            response.headers[HEADER] = await run_in_threadpool(activity.read, key)
            response.headers[ERROR_HEADER] = await run_in_threadpool(activity.error, key)
            response.headers[THUMBNAIL_HEADER] = await run_in_threadpool(
                activity.read, key + ":thumbnail"
            )
            response.headers["Cache-Control"] = "no-store"
            yield
            return
        if (
            request.method not in {"POST", "PUT", "PATCH", "DELETE"}
            or operation.startswith("spend/")
            or operation == "generation/cancel"
        ):
            yield
            return
        # Thumbnail work has its own lease and must never serialize the other agents.
        if operation.endswith("thumbnail"):
            key += ":thumbnail"
        token = await run_in_threadpool(activity.start, key, operation)
        request.state.generation_activity = (key, token)
    except RedisError as exc:
        raise HTTPException(
            503, "Cannot verify generation status. Please try again shortly."
        ) from exc

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(LEASE_SECONDS / 3)
            try:
                await run_in_threadpool(activity.renew, key, token)
            except RedisError:
                logging.getLogger(__name__).warning("Activity heartbeat unavailable; retrying")

    task = asyncio.create_task(heartbeat())
    try:
        yield
    except Exception as exc:
        # Speech adapters sanitize their errors. Never persist arbitrary exception
        # details, provider response bodies, or chained exceptions.
        message = str(exc) if isinstance(exc, SpeechUnavailable) else None
        logging.getLogger(__name__).warning(
            "Generation failed: resource=%s operation=%s error=%s detail=%s",
            parts[3],
            operation,
            type(exc).__name__,
            message or "Unavailable",
        )
        try:
            if not (await run_in_threadpool(activity.read, key)).startswith("cancelling/"):
                await run_in_threadpool(activity.failed, key, token, message)
        except RedisError:
            logging.getLogger(__name__).warning("Activity failure could not be recorded")
        raise
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await run_in_threadpool(activity.finish, key, token)
            except RedisError:
                logging.getLogger(__name__).warning(
                    "Activity cleanup unavailable; lease will expire"
                )
