from dataclasses import replace
from decimal import Decimal

import pytest
from fakes.animator import RecordingAnimator
from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fakes.spend import FixedBilling, InMemorySpend, RecordingUsageTracking
from fakes.storyboard_agent import RecordingStoryboardAgent

from app.courses.application.standalone import ApproveStandaloneLesson, PlanStandaloneLesson
from app.courses.application.standalone_dto import (
    ReviseStandaloneLessonRequest,
    StandaloneLessonRequest,
)
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.application.standalone_spend import GetStandaloneSpend, RefreshStandaloneSpend
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.speech import SpeechSettings
from app.courses.domain.spend import ModelCharge


def test_every_standalone_generation_stage_has_the_lesson_billing_scope(standalone):
    repo, uow, agent, _, created = standalone
    tracking = RecordingUsageTracking()
    request = ReviseStandaloneLessonRequest(created.id, created.owner_id, 0, created.description)
    planned = PlanStandaloneLesson(repo, uow, agent, tracking).execute(request)
    approved = ApproveStandaloneLesson(repo, uow).execute(
        replace(request, expected_revision=planned.revision)
    )
    board = GenerateStandaloneStoryboard(
        repo, uow, RecordingStoryboardAgent(uow), tracking
    ).execute(replace(request, expected_revision=approved.revision))
    artifacts = InMemorySpeechArtifacts(uow)
    voiced = GenerateStandaloneSpeech(
        repo, uow, RecordingSpeech(uow), artifacts, SpeechSettings("test-voice"), tracking=tracking
    ).execute(replace(request, expected_revision=board.revision))
    GenerateStandaloneAnimation(repo, uow, RecordingAnimator(uow), artifacts, tracking).execute(
        replace(request, expected_revision=voiced.revision)
    )
    assert tracking.calls == [
        (None, created.id, stage) for stage in ("lesson", "storyboard", "speech", "animation")
    ]
    assert not tracking.active


def test_standalone_spend_accumulates_and_is_owner_scoped(standalone):
    repo, uow, _, _, lesson = standalone
    spend = InMemorySpend()
    first = ModelCharge(
        "charge_first", None, lesson.id, "lesson", "openrouter", "model", usd=Decimal("0.01")
    )
    spend.save(first)
    spend.save(replace(first, id="charge_revision", usd=Decimal("0.02")))
    spend.save(replace(first, id="charge_pending", usd=None, provider_request_id="gen-pending"))
    reader = GetStandaloneSpend(repo, uow, spend)
    request = StandaloneLessonRequest(lesson.id, lesson.owner_id)
    response = reader.execute(request)
    assert response.total.known_usd == "0.03"
    assert response.total.calls == 3
    assert response.shared.calls == 0
    result = RefreshStandaloneSpend(repo, uow, spend, FixedBilling()).execute(request)
    assert result.total.known_usd == "0.032"
    assert result.total.calls == 3
    with pytest.raises(CourseNotFound):
        reader.execute(replace(request, owner_id="user_00000000-0000-0000-0000-000000000099"))
