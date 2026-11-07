from dataclasses import replace

import pytest
from fakes.animator import RecordingAnimator
from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fakes.storyboard_agent import RecordingStoryboardAgent
from fixtures.lesson_plan import infeasible_lesson_plan

from app.courses.application.generate_video import GenerateStandaloneVideo
from app.courses.application.standalone import ApproveStandaloneLesson
from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.domain.errors import CourseConflict
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator_model import AnimatorModel

OWNER = "user_00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("model", [None, *AnimatorModel])
@pytest.mark.parametrize("backend", tuple(AnimationBackend))
def test_video_runs_all_stages_and_reuses_saved_media_with_current_revisions(
    standalone, model, backend
):
    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    board, speech, animator = (
        RecordingStoryboardAgent(uow),
        RecordingSpeech(uow),
        RecordingAnimator(uow),
    )
    artifacts = InMemorySpeechArtifacts(uow)
    video = GenerateStandaloneVideo(
        ApproveStandaloneLesson(repo, uow),
        GenerateStandaloneStoryboard(repo, uow, board),
        GenerateStandaloneSpeech(repo, uow, speech, artifacts, SpeechSettings("test-voice")),
        GenerateStandaloneAnimation(repo, uow, animator, artifacts),
    )
    request = ReviseStandaloneLessonRequest(
        created.id,
        OWNER,
        planned.revision,
        generation_mode=GenerationMode.FAST,
        animator_model=model,
        animation_backend=backend,
    )
    result = video.execute(request)
    assert result.content.animation is not None
    assert repo.require_by_id(LessonId(created.id)).content.animation is not None
    assert board.calls[0].generation_mode is GenerationMode.FAST
    assert animator.calls[0].generation_mode is GenerationMode.FAST
    assert animator.calls[0].animator_model == model
    assert animator.calls[0].animation_backend == backend
    assert video.execute(replace(request, expected_revision=result.revision)) == result
    assert len(board.calls) == len(animator.calls) == 1
    with pytest.raises(CourseConflict):
        video.execute(request)


def test_script_approval_and_generation_share_one_use_case(standalone):
    from app.courses.application.generate_video import GenerateStandaloneScript

    repo, uow, _, planner, created = standalone
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0))
    agent = RecordingStoryboardAgent(uow)
    script = GenerateStandaloneScript(
        ApproveStandaloneLesson(repo, uow), GenerateStandaloneStoryboard(repo, uow, agent)
    )
    result = script.execute(
        ReviseStandaloneLessonRequest(
            created.id,
            OWNER,
            planned.revision,
            generation_mode=GenerationMode.FAST,
        )
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.approved
    assert saved.content.storyboard is not None
    assert result.revision == saved.revision
    assert agent.calls[0].generation_mode is GenerationMode.FAST
    assert (
        script.execute(ReviseStandaloneLessonRequest(created.id, OWNER, result.revision)) == result
    )
    assert len(agent.calls) == 1


def test_automatic_runs_from_draft_with_current_revisions_and_options(standalone):
    from app.courses.application.generate_automatic import GenerateAutomaticLesson

    repo, uow, planner_agent, planner, created = standalone
    board, speech, animator = (
        RecordingStoryboardAgent(uow),
        RecordingSpeech(uow),
        RecordingAnimator(uow),
    )
    artifacts = InMemorySpeechArtifacts(uow)
    service = GenerateAutomaticLesson(
        planner,
        GenerateStandaloneVideo(
            ApproveStandaloneLesson(repo, uow),
            GenerateStandaloneStoryboard(repo, uow, board),
            GenerateStandaloneSpeech(repo, uow, speech, artifacts, SpeechSettings("test-voice")),
            GenerateStandaloneAnimation(repo, uow, animator, artifacts),
        ),
    )
    request = ReviseStandaloneLessonRequest(
        created.id,
        OWNER,
        created.revision,
        "Teach a beginner",
        generation_mode=GenerationMode.FAST,
        animator_model=AnimatorModel.OPUS_FAST,
        animation_backend=AnimationBackend.DIRECT,
    )
    result = service.execute(request)
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.animation is not None
    assert saved.approved
    assert result.revision == saved.revision
    assert planner_agent.calls[0].message == "Teach a beginner"
    assert planner_agent.calls[0].generation_mode == GenerationMode.FAST
    assert board.calls[0].generation_mode == GenerationMode.FAST
    assert animator.calls[0].animator_model == AnimatorModel.OPUS_FAST
    assert animator.calls[0].animation_backend == AnimationBackend.DIRECT
    with pytest.raises(CourseConflict):
        service.execute(request)
    assert len(planner_agent.calls) == len(board.calls) == len(animator.calls) == 1


def test_automatic_stops_at_an_infeasible_outline_before_any_media_calls(standalone):
    from app.courses.application.generate_automatic import GenerateAutomaticLesson

    repo, uow, agent, planner, created = standalone
    before = repo.require_by_id(LessonId(created.id))
    agent.plan = infeasible_lesson_plan(before.brief())
    board, speech, animator = (
        RecordingStoryboardAgent(uow),
        RecordingSpeech(uow),
        RecordingAnimator(uow),
    )
    artifacts = InMemorySpeechArtifacts(uow)
    service = GenerateAutomaticLesson(
        planner,
        GenerateStandaloneVideo(
            ApproveStandaloneLesson(repo, uow),
            GenerateStandaloneStoryboard(repo, uow, board),
            GenerateStandaloneSpeech(repo, uow, speech, artifacts, SpeechSettings("test-voice")),
            GenerateStandaloneAnimation(repo, uow, animator, artifacts),
        ),
    )
    result = service.execute(ReviseStandaloneLessonRequest(created.id, OWNER, 0, "Plan"))
    saved = repo.require_by_id(LessonId(created.id))
    assert result.content.plan.feasibility_status == "infeasible"
    assert result.content.plan.recommended_video_minutes == agent.plan.minimum_video_minutes
    assert result.revision == saved.revision == 1
    assert saved.content.plan == agent.plan
    assert saved.content.minutes == before.content.minutes
    assert not saved.approved
    assert not board.calls
    assert not speech.calls
    assert not animator.calls


def test_switching_flow_preserves_finished_content_and_omission_keeps_flow(completed_standalone):
    from app.courses.domain.standalone import LessonFlow

    _, before = completed_standalone
    automatic = before.update_details(
        before.content.title,
        before.description,
        before.content.minutes,
        flow=LessonFlow.AUTOMATIC,
    )
    assert automatic.flow == LessonFlow.AUTOMATIC
    assert automatic.content == before.content
    assert automatic.approved == before.approved
    assert automatic.revision == before.revision + 1
    assert (
        automatic.update_details(
            automatic.content.title, automatic.description, automatic.content.minutes
        )
        is automatic
    )
