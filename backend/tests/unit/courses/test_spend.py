from dataclasses import replace
from decimal import Decimal

import pytest
from fakes.spend import FixedBilling, InMemorySpend, RecordingUsageTracking
from fakes.syllabus import InMemoryConversations
from fixtures.syllabus import COURSE_ID, LESSON_ID, make_planned_course

from app.courses.application.generate_lesson import GenerateLesson, GenerateLessonRequest
from app.courses.application.spend import GetCourseSpend, RefreshCourseSpend, SpendRequest
from app.courses.domain.errors import CourseError, CourseNotFound
from app.courses.domain.spend import GenerationStep, ModelCharge, sum_charges
from app.courses.ports.syllabus_agent import SyllabusConversation


def charge(identity="charge_1", **changes):
    return replace(
        ModelCharge(identity, COURSE_ID, LESSON_ID, "lesson", "openrouter", "model"), **changes
    )


@pytest.mark.parametrize("usd", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1")])
def test_money_rejects_invalid_amounts(usd):
    with pytest.raises(CourseError):
        charge(usd=usd)


def test_rejects_negative_tokens_and_unpriced_estimates():
    with pytest.raises(CourseError):
        charge(input_tokens=-1)
    with pytest.raises(CourseError):
        charge(estimated=True)
    with pytest.raises(CourseError):
        charge(credits=Decimal("-1"))


def test_totals_keep_decimal_precision_and_pending_distinct_from_zero():
    result = sum_charges((charge(usd=Decimal("0.000000000001")), charge("charge_2")))
    assert result.known_usd == Decimal("0.000000000001")
    assert result.pending_calls == 1
    assert result.calls == 2
    assert sum_charges(()).known_usd == 0


def test_course_sums_lessons_and_shared_planning_without_resetting_history(lesson_generation):
    _, courses, _, _, _ = lesson_generation
    spend = InMemorySpend()
    for item in (
        charge(usd=Decimal("0.1"), input_tokens=10),
        charge("charge_2", stage="storyboard", usd=Decimal("0.2"), output_tokens=20),
        charge("charge_3", lesson_id=None, stage="syllabus", usd=Decimal("0.03")),
        charge("charge_4", provider="elevenlabs", stage="speech", credits=Decimal(50)),
        charge("charge_5", lesson_id="other", usd=Decimal("0.05"), estimated=True),
    ):
        spend.save(item)
    reader = GetCourseSpend(courses, spend)
    result = reader.execute(SpendRequest(COURSE_ID))
    assert Decimal(result.total.known_usd) == Decimal("0.38")
    assert result.total.pending_calls == 1
    assert result.total.estimated_calls == 1
    assert result.total.input_tokens == 10
    assert result.total.output_tokens == 20
    assert Decimal(result.shared.known_usd) == Decimal("0.03")
    assert sum(Decimal(ls.total.known_usd) for ls in result.lessons) + Decimal(
        result.shared.known_usd
    ) == Decimal(result.total.known_usd)
    spend.save(charge("charge_6", usd=Decimal("0.004")))
    assert Decimal(reader.execute(SpendRequest(COURSE_ID)).total.known_usd) == Decimal("0.384")


def test_refresh_reconciles_once_without_adding_a_second_call(lesson_generation):
    _, courses, _, uow, _ = lesson_generation
    spend, billing = InMemorySpend(), FixedBilling()
    spend.save(charge(provider_request_id="gen-pending"))
    service = RefreshCourseSpend(courses, spend, billing, uow)
    result = service.execute(SpendRequest(COURSE_ID))
    assert result.total.known_usd == "0.002"
    assert result.total.pending_calls == 0
    assert result.total.calls == 1
    service.execute(SpendRequest(COURSE_ID))
    assert len(billing.calls) == 1


def test_unidentified_failed_requests_do_not_starve_reconcilable_charges(lesson_generation):
    _, courses, _, uow, _ = lesson_generation
    spend, billing = InMemorySpend(), FixedBilling()
    for index in range(100):
        spend.save(charge(f"charge_unknown_{index}"))
    spend.save(charge("charge_known", provider_request_id="gen-pending"))
    result = RefreshCourseSpend(courses, spend, billing, uow).execute(SpendRequest(COURSE_ID))
    assert result.total.known_usd == "0.002"
    assert result.total.pending_calls == 100
    assert len(billing.calls) == 1


def test_spend_requires_an_existing_course(lesson_generation):
    _, courses, _, _, _ = lesson_generation
    with pytest.raises(CourseNotFound):
        GetCourseSpend(courses, InMemorySpend()).execute(
            SpendRequest("course_00000000-0000-0000-0000-000000000099")
        )


def test_cached_lesson_has_no_new_tracking_scope(lesson_generation):
    _, courses, agent, uow, _ = lesson_generation
    conversations, tracking = InMemoryConversations(), RecordingUsageTracking()
    _, curriculum = make_planned_course()
    conversations.save(SyllabusConversation(COURSE_ID, 1, curriculum=curriculum), 0)
    service = GenerateLesson(courses, conversations, agent, uow, tracking)
    service.execute(GenerateLessonRequest(COURSE_ID, LESSON_ID))
    service.execute(GenerateLessonRequest(COURSE_ID, LESSON_ID))
    assert tracking.calls == [(COURSE_ID, LESSON_ID, "lesson")]
    assert not tracking.active


@pytest.mark.parametrize(
    "start,end", [(-1, None), (10, 9), (float("nan"), None), (0, float("inf"))]
)
def test_generation_timing_rejects_invalid_timestamps(start, end):
    with pytest.raises(CourseError):
        GenerationStep("step_invalid", COURSE_ID, LESSON_ID, "lesson", start, end)


def test_generation_timing_requires_an_owner():
    with pytest.raises(CourseError):
        GenerationStep("step_invalid", None, None, "lesson", 10)


def test_spend_exposes_running_steps_before_any_billable_calls(lesson_generation):
    _, courses, _, _, _ = lesson_generation
    ledger = InMemorySpend()
    step = GenerationStep("step_assets", COURSE_ID, LESSON_ID, "assets", 100)
    ledger.save_step(step)
    reader = GetCourseSpend(courses, ledger)
    running = reader.execute(SpendRequest(COURSE_ID))
    assert running.total.calls == 0
    assert running.steps[0].stage == "assets"
    assert running.steps[0].started_at == 100
    assert running.steps[0].finished_at is None
    ledger.save_step(replace(step, finished_at=175))
    finished = reader.execute(SpendRequest(COURSE_ID))
    assert len(finished.steps) == 1
    assert finished.steps[0].finished_at == 175
    assert finished.total.known_usd == "0"
