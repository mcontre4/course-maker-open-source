import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.courses.domain.spend import GenerationStep, ModelCharge
from app.courses.ports.spend import SpendRepository


def amount(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() and parsed >= 0 else None
    except InvalidOperation:
        return None


def usage_model(payload: dict[str, Any], fallback: str = "unknown") -> str:
    model = payload.get("model", payload.get("model_id")) or fallback
    if (
        payload.get("service_tier") in ("fast", "priority") or fallback.endswith(":fast")
    ) and not model.endswith(":fast"):
        model += ":fast"
    return str(model)


def openrouter_charge(charge: ModelCharge, payload: dict[str, Any]) -> ModelCharge:
    response = payload.get("response", payload)
    usage = response.get("usage") or {}
    return replace(
        charge,
        provider_request_id=response.get("id") or charge.provider_request_id,
        model=usage_model(response, charge.model),
        usd=amount(usage.get("cost")),
        input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0,
        output_tokens=usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0,
    )


class ProviderBilling:
    def __init__(
        self, client: httpx.Client, openrouter_key: str, eleven_usd_per_credit: Decimal | None
    ):
        self._client, self._key, self._rate = client, openrouter_key, eleven_usd_per_credit

    def resolve(self, charge: ModelCharge) -> ModelCharge:
        if charge.provider == "elevenlabs" and charge.credits is not None and self._rate:
            return replace(charge, usd=charge.credits * self._rate, estimated=True)
        if charge.provider != "openrouter" or not charge.provider_request_id or not self._key:
            return charge
        try:
            response = self._client.get(
                "https://openrouter.ai/api/v1/generation",
                params={"id": charge.provider_request_id},
                headers={"Authorization": "Bearer " + self._key},
            )
            response.raise_for_status()
            cost = amount(response.json()["data"].get("total_cost"))
            return replace(charge, usd=cost) if cost is not None else charge
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            return charge


class ProviderUsageTracking:
    """Injected instrumentation. Context is isolated across concurrent operations."""

    def __init__(self, spend: SpendRepository, billing: ProviderBilling) -> None:
        self._spend, self._billing = spend, billing
        self._scope: ContextVar[tuple[str | None, str | None, str] | None] = ContextVar(
            "model_usage_scope", default=None
        )

    @contextmanager
    def scope(self, course_id: str | None, lesson_id: str | None, stage: str) -> Iterator[None]:
        token = self._scope.set((course_id, lesson_id, stage))
        try:
            # These generation boundaries record their individual provider stages.
            if stage in {"animation", "storyboard"}:
                yield
            else:
                with self._step():
                    yield
        finally:
            self._scope.reset(token)

    @contextmanager
    def _step(self, backend: str | None = None) -> Iterator[None]:
        scope = self._scope.get()
        if scope is None:
            yield
            return
        step = GenerationStep("step_" + str(uuid4()), *scope, time.time(), backend=backend)
        self._spend.save_step(step)
        try:
            yield
        finally:
            self._spend.save_step(replace(step, finished_at=max(step.started_at, time.time())))

    @contextmanager
    def worker(self, stage: str, *, backend: str | None = None) -> Iterator[None]:
        scope = self._scope.get()
        if scope is None:
            yield
            return
        token = self._scope.set((*scope[:2], stage))
        try:
            with self._step(backend):
                yield
        finally:
            self._scope.reset(token)

    def request(self, request: httpx.Request) -> None:
        scope = self._scope.get()
        if scope is None or request.method != "POST":
            return
        provider = "openrouter" if request.url.host == "openrouter.ai" else "elevenlabs"
        payload = json.loads(request.content)
        charge = ModelCharge(
            "charge_" + str(uuid4()),
            *scope,
            provider,
            usage_model(payload),
        )
        # Persist intent before I/O, including ambiguous failures with no response.
        self._spend.save(charge)
        request.extensions["model_charge"] = charge

    def response(self, response: httpx.Response) -> None:
        charge = response.request.extensions.get("model_charge")
        if not isinstance(charge, ModelCharge):
            return
        if 400 <= response.status_code < 500 and response.status_code != 408:
            self._spend.save(replace(charge, usd=Decimal(0)))
            return
        if response.is_error:
            return
        if charge.provider == "openrouter":
            response.read()
            try:
                charge = openrouter_charge(charge, response.json())
            except (ValueError, TypeError, AttributeError):
                return  # Durable pending entry remains visible.
        else:
            charge = replace(
                charge,
                provider_request_id=response.headers.get("request-id"),
                credits=amount(response.headers.get("character-cost")),
            )
        self._spend.save(charge)
        if charge.usd is None:
            self._spend.save(self._billing.resolve(charge))

    async def async_request(self, request: httpx.Request) -> None:
        self.request(request)

    async def async_response(self, response: httpx.Response) -> None:
        await response.aread()
        self.response(response)

    def ingest_animation(self, path: Path, *, resolve: bool = True) -> None:
        scope = self._scope.get()
        if scope is None or not path.exists():
            return
        events: dict[str, dict[str, Any]] = {}
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
                previous = events.get(event["id"], {})
                event["response"] = {**previous.get("response", {}), **event.get("response", {})}
                events[event["id"]] = event
            except (ValueError, KeyError, TypeError):
                continue
        for event in events.values():
            try:
                charge = ModelCharge(event["id"], *scope, "openrouter", usage_model(event))
                charge = openrouter_charge(charge, event.get("response", {}))
            except (ValueError, KeyError, TypeError):
                continue
            self._spend.save(charge)
            if resolve and charge.usd is None:
                self._spend.save(self._billing.resolve(charge))
