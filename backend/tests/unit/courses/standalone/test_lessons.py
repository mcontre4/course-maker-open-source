from dataclasses import replace

import pytest
from fakes.animator import RecordingAnimator
from fakes.courses import RecordingUnitOfWork, SequenceIds
from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fakes.standalone import InMemoryStandaloneLessons
from fakes.storyboard_agent import RecordingStoryboardAgent
from fixtures.speech import legacy_speech

from app.courses.application.standalone import (
    ApproveStandaloneLesson,
    CreateStandaloneLesson,
    GetStandaloneLesson,
    ListStandaloneLessons,
)
from app.courses.application.standalone_dto import (
    CreateStandaloneLessonRequest,
    ListStandaloneLessonsRequest,
    ReviseStandaloneLessonRequest,
    StandaloneLessonRequest,
)
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import LessonId
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.lesson_agent import LessonGenerationUnavailable

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"


def test_completed_legacy_audio_refreshes_without_regenerating_outline(voiced_standalone):
    service, repo, provider, artifacts, before = voiced_standalone
    older = replace(
        before,
        content=replace(
            legacy_speech(before.content, artifacts), video_url="https://example.com/old.mp4"
        ),
    )
    repo.save(older)

    response = service.execute(
        ReviseStandaloneLessonRequest(str(before.content.id), OWNER, before.revision)
    )

    saved = repo.require_by_id(before.content.id)
    assert saved.revision == before.revision + 1
    assert saved.content.alignment != older.content.alignment
    assert saved.content.plan == older.content.plan
    assert saved.content.storyboard == older.content.storyboard
    assert saved.content.animation is None and saved.content.video_url is None
    assert len(provider.calls) == 4
    assert service.execute(
        ReviseStandaloneLessonRequest(str(before.content.id), OWNER, response.revision)
    ) == response
    assert len(provider.calls) == 4


def test_three_minute_lesson_planning_refinement_approval_and_full_pipeline(standalone):
    repo, uow, agent, planner, created = standalone
    first = planner.execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, 0, created.description)
    )
    refined = planner.execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, 1, "Use water as the example")
    )
    assert agent.calls[1].previous_plan is not None
    assert agent.calls[1].conversation[0][0] == created.description
    assert agent.calls[1].message == "Use water as the example"
    assert refined.content.plan == first.content.plan
    approved = ApproveStandaloneLesson(repo, uow).execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, 2)
    )
    storyboard_agent = RecordingStoryboardAgent(uow)
    storyboard = GenerateStandaloneStoryboard(repo, uow, storyboard_agent)
    board = storyboard.execute(ReviseStandaloneLessonRequest(created.id, OWNER, approved.revision))
    speech_agent = RecordingSpeech(uow)
    artifacts = InMemorySpeechArtifacts(uow)
    speech = GenerateStandaloneSpeech(
        repo, uow, speech_agent, artifacts, SpeechSettings("test-voice")
    )
    voiced = speech.execute(ReviseStandaloneLessonRequest(created.id, OWNER, board.revision))
    cached = speech.execute(ReviseStandaloneLessonRequest(created.id, OWNER, voiced.revision))
    assert cached.revision == voiced.revision
    assert len(speech_agent.calls) == 2
    animator = RecordingAnimator(uow)
    result = GenerateStandaloneAnimation(repo, uow, animator, artifacts).execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, voiced.revision)
    )
    assert result.content.animation is not None
    assert result.owner_id == OWNER
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.animation is not None
    assert saved.content.minutes == 3
    # A chat revision invalidates every downstream artifact and approval.
    revised = planner.execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, result.revision, "Remove the example")
    )
    assert not revised.approved
    assert revised.content.storyboard is None
    assert revised.content.alignment is None
    assert revised.content.animation is None


def test_other_owner_cannot_read_list_plan_approve_or_generate(standalone):
    repo, uow, agent, planner, created = standalone
    assert ListStandaloneLessons(repo, uow).execute(ListStandaloneLessonsRequest(OTHER)).items == ()
    with pytest.raises(CourseNotFound):
        GetStandaloneLesson(repo, uow).execute(StandaloneLessonRequest(created.id, OTHER))
    for service in (
        planner,
        ApproveStandaloneLesson(repo, uow),
        GenerateStandaloneStoryboard(repo, uow, RecordingStoryboardAgent(uow)),
    ):
        with pytest.raises(CourseNotFound):
            service.execute(ReviseStandaloneLessonRequest(created.id, OTHER, 0, "Change"))
    assert not agent.calls


def test_stale_request_and_missing_approval_are_rejected_before_paid_calls(standalone):
    repo, uow, agent, planner, created = standalone
    with pytest.raises(CourseConflict):
        planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 42, "Change"))
    with pytest.raises(CourseConflict):
        GenerateStandaloneStoryboard(repo, uow, RecordingStoryboardAgent(uow)).execute(
            ReviseStandaloneLessonRequest(created.id, OWNER, 0)
        )
    assert not agent.calls


def test_failure_and_concurrent_edit_preserve_saved_lesson(standalone):
    repo, uow, agent, planner, created = standalone
    agent.error = LessonGenerationUnavailable("unavailable")
    with pytest.raises(LessonGenerationUnavailable):
        planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Change"))
    assert repo.require_by_id(LessonId(created.id)).revision == 0
    agent.error = None

    def concurrent_change():
        saved = repo.require_by_id(LessonId(created.id))
        repo.save(replace(saved, revision=1))

    agent.during_run = concurrent_change
    with pytest.raises(CourseConflict):
        planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Change"))
    assert repo.require_by_id(LessonId(created.id)).content.plan is None


@pytest.mark.parametrize("minutes", [0, 11, 3.5, True])
def test_standalone_duration_invariant(minutes):
    repo = InMemoryStandaloneLessons()
    service = CreateStandaloneLesson(repo, RecordingUnitOfWork(repo), SequenceIds())
    with pytest.raises(CourseError):
        service.execute(CreateStandaloneLessonRequest(OWNER, "Bonds", "Explain chemistry", minutes))
    assert not repo.items


def test_ten_minute_limit_also_applies_to_generated_outline(standalone):
    from fixtures.lesson_plan import lesson_plan

    from app.courses.domain.lesson_plan import PlanGeneration

    repo, _, _, _, created = standalone
    lesson = repo.require_by_id(LessonId(created.id))
    ten_minutes = replace(lesson, content=replace(lesson.content, minutes=10))
    plan = lesson_plan(ten_minutes.brief())
    too_long = replace(plan, feasibility_status=None, beats=(replace(plan.beats[0], seconds=620),))
    with pytest.raises(CourseError, match="10 minutes"):
        ten_minutes.revise("Keep it short", too_long, PlanGeneration("test", 1, 0, 100))


def test_partial_narration_failure_resumes_without_regenerating_saved_audio(standalone):
    from app.courses.ports.speech import SpeechUnavailable

    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    approved = ApproveStandaloneLesson(repo, uow).execute(
        ReviseStandaloneLessonRequest(created.id, OWNER, planned.revision)
    )
    agent = RecordingStoryboardAgent(uow)
    boards = GenerateStandaloneStoryboard(repo, uow, agent)
    board = boards.execute(ReviseStandaloneLessonRequest(created.id, OWNER, approved.revision))
    boards.execute(ReviseStandaloneLessonRequest(created.id, OWNER, board.revision))
    assert len(agent.calls) == 1
    speech_agent = RecordingSpeech(uow)
    speech_agent.fail_on_call = 2
    artifacts = InMemorySpeechArtifacts(uow)
    speech = GenerateStandaloneSpeech(
        repo, uow, speech_agent, artifacts, SpeechSettings("test-voice")
    )
    request = ReviseStandaloneLessonRequest(created.id, OWNER, board.revision)
    with pytest.raises(SpeechUnavailable):
        speech.execute(request)
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.revision == board.revision
    assert saved.content.storyboard is not None
    assert saved.content.alignment is None
    speech_agent.fail_on_call = None
    resumed = speech.execute(request)
    assert resumed.content.alignment is not None
    assert len(speech_agent.calls) == 3
