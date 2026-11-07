import asyncio
from decimal import Decimal

import httpx
import pytest
from fakes.spend import InMemorySpend

from app.courses.adapters.ai.spend import ProviderBilling, ProviderUsageTracking


def test_openrouter_records_every_request_including_retries_and_fetches_missing_cost():
    ledger = InMemorySpend()

    def provider(request):
        if request.method == "GET":
            assert request.url.params["id"] == "gen-123"
            return httpx.Response(200, json={"data": {"total_cost": 0.000012345678}})
        return httpx.Response(
            200,
            json={
                "id": "gen-123",
                "model": "any-provider/model",
                "usage": {"input_tokens": 100, "output_tokens": 25},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(provider)) as billing_client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(billing_client, "key", None))

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(provider),
                event_hooks={
                    "request": [tracking.async_request],
                    "response": [tracking.async_response],
                },
            ) as client:
                with tracking.scope("course", "lesson", "storyboard"):
                    await client.post(
                        "https://openrouter.ai/api/v1/responses", json={"model": "model"}
                    )
                    await client.post(
                        "https://openrouter.ai/api/v1/responses", json={"model": "model"}
                    )

        asyncio.run(run())
    charges = ledger.list_by_course_id("course")
    assert len(charges) == 2
    assert all(c.usd == Decimal("0.000012345678") for c in charges)
    assert charges[0].input_tokens == 100
    assert charges[0].output_tokens == 25
    assert charges[0].model == "any-provider/model"
    assert charges[0].lesson_id == "lesson"


@pytest.mark.parametrize("status,expected", [(400, Decimal(0)), (429, Decimal(0)), (500, None)])
def test_definitive_rejections_are_zero_and_ambiguous_failures_stay_pending(status, expected):
    ledger = InMemorySpend()
    with httpx.Client() as billing_client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(billing_client, "", None))
        with (
            httpx.Client(
                transport=httpx.MockTransport(lambda request: httpx.Response(status)),
                event_hooks={"request": [tracking.request], "response": [tracking.response]},
            ) as client,
            tracking.scope("course", "lesson", "lesson"),
        ):
            client.post("https://openrouter.ai/api/v1/responses", json={"model": "model"})
    assert ledger.list_by_course_id("course")[0].usd == expected


def test_speech_uses_reported_credits_with_configured_rate_and_context_does_not_leak():
    ledger = InMemorySpend()
    with httpx.Client() as billing_client:
        tracking = ProviderUsageTracking(
            ledger, ProviderBilling(billing_client, "", Decimal("0.0003"))
        )
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    headers={"request-id": "speech-1", "character-cost": "50"},
                    content=b"audio",
                )
            ),
            event_hooks={"request": [tracking.request], "response": [tracking.response]},
        ) as client:
            with tracking.scope("course", "lesson", "speech"):
                client.post(
                    "https://api.elevenlabs.io/v1/text-to-dialogue/with-timestamps",
                    json={"model_id": "eleven_v4"},
                )
            client.post(
                "https://api.elevenlabs.io/v1/text-to-dialogue/with-timestamps",
                json={"model_id": "eleven_v4"},
            )
    charges = ledger.list_by_course_id("course")
    assert len(charges) == 1
    assert charges[0].estimated
    assert charges[0].credits == 50
    assert charges[0].usd == Decimal("0.0150")


def test_animation_billing_replay_deduplicates_stream_events(tmp_path):
    ledger = InMemorySpend()
    path = tmp_path / "usage.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"id":"charge_animation","model":"model"}',
                '{"id":"charge_animation","model":"model","response":{"id":"gen-1","usage":{"cost":0.002,"input_tokens":10,"output_tokens":20}}}',
            ]
        )
    )
    with httpx.Client() as client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(client, "", None))
        with tracking.scope("course", "lesson", "animation"):
            tracking.ingest_animation(path)
            tracking.ingest_animation(path)
    charges = ledger.list_by_course_id("course")
    assert len(charges) == 1
    assert charges[0].usd == Decimal("0.002")
    assert charges[0].output_tokens == 20


@pytest.mark.integration
def test_codex_steps_are_visible_during_work_and_close_on_failure():
    ledger = InMemorySpend()
    with httpx.Client() as client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(client, "", None))
        with tracking.scope("course", "lesson", "animation"):
            with tracking.worker("assets"):
                running = ledger.list_steps(course_id="course")
                assert len(running) == 1
                assert running[0].stage == "assets"
                assert running[0].finished_at is None
                assert ledger.list_by_course_id("course") == ()
            with pytest.raises(RuntimeError), tracking.worker("animation"):
                raise RuntimeError("Worker failed")
        finished = ledger.list_steps(course_id="course")
        assert [s.stage for s in finished] == ["assets", "animation"]
        assert all(s.finished_at >= s.started_at for s in finished)
        with tracking.worker("assets"):
            pass  # Context must not leak outside the original operation.
        assert len(ledger.list_steps(course_id="course")) == 2


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["assets", "visual_review", "animation_repair"])
def test_live_codex_usage_stays_in_its_worker_stage(tmp_path, stage):
    ledger = InMemorySpend()
    path = tmp_path / "usage.jsonl"
    path.write_text('{"id":"asset_call","model":"model","response":{"usage":{"cost":0.25}}}\n')
    with httpx.Client() as client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(client, "", None))
        with tracking.scope("course", "lesson", "animation"), tracking.worker(stage):
            tracking.ingest_animation(path, resolve=False)
            assert ledger.list_steps(course_id="course")[0].finished_at is None
            assert ledger.list_by_course_id("course")[0].stage == stage
            tracking.ingest_animation(path)
    assert len(ledger.list_by_course_id("course")) == 1
    assert ledger.list_by_course_id("course")[0].usd == Decimal("0.25")


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["assets", "animation", "visual_review", "animation_repair"])
def test_direct_call_records_engine_before_billing_and_returns_it_in_spend(stage):
    from app.courses.adapters.ai.direct_animation import DirectAnimationCall
    from app.courses.adapters.http.spend import CourseSpendView
    from app.courses.application.spend import spend_response

    ledger = InMemorySpend()

    def provider(request):
        active = ledger.list_steps(lesson_id="lesson")
        assert len(active) == 1
        assert active[0].backend == "direct"
        assert active[0].finished_at is None
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "result"}}],
            },
        )

    with httpx.Client() as billing_client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(billing_client, "", None))

        def clients():
            return httpx.Client(transport=httpx.MockTransport(provider))

        llm = DirectAnimationCall(clients, "key", "model", "high", tracking)
        with tracking.scope(None, "lesson", "animation"):
            assert llm.complete("system", [], stage) == "result"

    steps = ledger.list_steps(lesson_id="lesson")
    assert steps[0].finished_at is not None
    view = CourseSpendView.model_validate(spend_response((), steps))
    assert view.model_dump(by_alias=True)["steps"][0]["backend"] == "direct"


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"model": "model"}, "model"),
        ({"model": "model:fast"}, "model:fast"),
        ({"model": "model", "service_tier": "fast"}, "model:fast"),
        ({"model": "model", "service_tier": "priority"}, "model:fast"),
    ],
)
def test_fast_usage_survives_provider_base_model_response(payload, expected):
    ledger = InMemorySpend()
    with httpx.Client() as billing_client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(billing_client, "", None))
        with (
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json={"model": "model", "usage": {"cost": 0.001}}
                    )
                ),
                event_hooks={"request": [tracking.request], "response": [tracking.response]},
            ) as client,
            tracking.scope("course", "lesson", "storyboard"),
        ):
            client.post("https://openrouter.ai/api/v1/responses", json=payload)
    assert ledger.list_by_course_id("course")[0].model == expected


@pytest.mark.integration
def test_offline_renderer_records_timing_without_a_provider_backend(tmp_path):
    from app.courses.adapters.ai.animator import AnimationWorker

    ledger = InMemorySpend()
    observed = []

    def run(job, kind, args, prompt, name):
        active = [s for s in ledger.list_steps(course_id="course") if s.finished_at is None]
        assert len(active) == 1
        assert active[0].backend is None
        observed.append(active[0].stage)

    with httpx.Client() as client:
        tracking = ProviderUsageTracking(ledger, ProviderBilling(client, "", None))
        worker = AnimationWorker(tmp_path, tmp_path, "", tracking=tracking, command_runner=run)
        with tracking.scope("course", "lesson", "animation"):
            for name in ("render-review", "render-final"):
                worker.run_job(tmp_path, "validate", ["node"], None, name)
    assert observed == ["render", "render"]
    assert all(s.finished_at is not None for s in ledger.list_steps(course_id="course"))
