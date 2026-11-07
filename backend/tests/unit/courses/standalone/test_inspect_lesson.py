from dataclasses import replace
from decimal import Decimal

import pytest
from fakes.authentication import MutableAuthClock
from fakes.courses import InMemoryCourses
from fakes.spend import FixedBilling, InMemorySpend
from fixtures.syllabus import COURSE_ID, LESSON_ID

from app.courses.application.inspect_lesson import InspectLesson, InspectLessonRequest
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.spend import GenerationStep, ModelCharge, generation_seconds


@pytest.mark.parametrize(
    "intervals,now,expected",
    [
        ([], 500, None),
        ([(0, 0)], 500, 0),
        ([(100, 200), (150, 180), (190, 250), (300, 330)], 500, 180),
        ([(100, 150), (150, 200)], 500, 100),
        ([(100, 150), (200, None)], 230, 80),
        ([(100, None)], 90, 0),
    ],
)
def test_total_time_counts_parallel_intervals_once_and_excludes_idle(intervals, now, expected):
    steps = tuple(
        GenerationStep(f"step_{i}", None, LESSON_ID, "lesson", start, end)
        for i, (start, end) in enumerate(intervals)
    )
    assert generation_seconds(steps, now) == expected


def test_internal_inspection_reads_other_owners_and_reconciles_without_generating(standalone):
    lessons, uow, agent, _, created = standalone
    ledger, billing, clock = InMemorySpend(), FixedBilling(), MutableAuthClock()
    charge = ModelCharge(
        "charge_internal",
        None,
        created.id,
        "lesson",
        "openrouter",
        "model",
        provider_request_id="gen-pending",
    )
    ledger.save(charge)
    ledger.save_step(GenerationStep("step_internal", None, created.id, "lesson", 100, 160))
    service = InspectLesson(lessons, InMemoryCourses(), uow, ledger, billing, clock)
    before = service.execute(InspectLessonRequest(created.id))
    assert before.title == "Chemical bonds"
    assert before.generation_seconds == 60
    assert not before.generation_active
    assert before.spend.total.pending_calls == 1
    assert billing.calls == []
    result = service.execute(InspectLessonRequest(created.id, refresh=True))
    assert result.spend.total.known_usd == "0.002"
    assert ledger.list_by_lesson_id(created.id)[0].usd == Decimal("0.002")
    assert agent.calls == []
    service.execute(InspectLessonRequest(created.id, refresh=True))
    assert len(billing.calls) == 1


def test_internal_inspection_running_and_missing_timing(standalone):
    lessons, uow, _, _, created = standalone
    ledger, clock = InMemorySpend(), MutableAuthClock()
    service = InspectLesson(lessons, InMemoryCourses(), uow, ledger, FixedBilling(), clock)
    assert service.execute(InspectLessonRequest(created.id)).generation_seconds is None
    ledger.save_step(
        GenerationStep("step_running", None, created.id, "animation", clock.timestamp - 35)
    )
    result = service.execute(InspectLessonRequest(created.id))
    assert result.generation_seconds == 35
    assert result.generation_active
    with pytest.raises(CourseNotFound):
        service.execute(InspectLessonRequest("lesson_00000000-0000-0000-0000-000000000099"))


def test_course_inspection_excludes_shared_costs_and_other_lessons(standalone, lesson_generation):
    lessons, _, _, _, _ = standalone
    _, courses, _, uow, course = lesson_generation
    ledger, billing = InMemorySpend(), FixedBilling()
    charge = ModelCharge("course_charge", COURSE_ID, LESSON_ID, "lesson", "openrouter", "model")
    for item in (
        replace(charge, usd=Decimal("0.1")),
        replace(charge, id="shared", lesson_id=None, usd=Decimal("10")),
        replace(charge, id="other", lesson_id="lesson_other", usd=Decimal("20")),
    ):
        ledger.save(item)
    for lesson_id in (LESSON_ID, "lesson_other", None):
        ledger.save_step(
            GenerationStep(f"step_{lesson_id}", COURSE_ID, lesson_id, "lesson", 100, 130)
        )
    service = InspectLesson(lessons, courses, uow, ledger, billing, MutableAuthClock())
    result = service.execute(InspectLessonRequest(LESSON_ID, COURSE_ID, refresh=True))
    assert result.title == course.lesson(LESSON_ID).title
    assert result.spend.total.known_usd == "0.1"
    assert result.generation_seconds == 30
    assert len(result.spend.steps) == 1
    with pytest.raises(CourseNotFound):
        service.execute(
            InspectLessonRequest("lesson_00000000-0000-0000-0000-000000000099", COURSE_ID)
        )
