from dataclasses import replace

import pytest
from fakes.courses import SequenceIds

from app.courses.application.generate_automatic import GenerateAutomaticLesson
from app.courses.application.generate_video import GenerateStandaloneScript
from app.courses.application.standalone import CreateStandaloneLesson, UpdateStandaloneLesson
from app.courses.application.standalone_dto import (
    CreateStandaloneLessonRequest,
    ReviseStandaloneLessonRequest,
    UpdateStandaloneLessonRequest,
)
from app.courses.application.style_dto import style_input
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.style import LessonStyle
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.storyboard_agent import StoryboardGenerationUnavailable


@pytest.mark.parametrize("restart", ["script", "speech", "animation"])
def test_video_regenerates_selected_stage_and_dependents_with_latest_options(
    video_pipeline, restart
):
    video, repo, board, speech, animator, artifacts, result = video_pipeline
    before = repo.require_by_id(LessonId(result.id))
    old_audio = {
        s.audio_key: artifacts.objects[s.audio_key] for s in before.content.alignment.scenes
    }
    speech_calls = len(speech.calls)
    updated = video.execute(
        ReviseStandaloneLessonRequest(
            result.id,
            result.owner_id,
            result.revision,
            generation_mode=GenerationMode.PRO,
            animator_model=AnimatorModel.OPUS_FAST,
            regenerate_from=restart,
        )
    )
    saved = repo.require_by_id(LessonId(result.id))
    assert updated.revision == saved.revision > before.revision
    assert saved.content.plan == before.content.plan
    assert len(board.calls) == (2 if restart == "script" else 1)
    assert len(speech.calls) == speech_calls * (2 if restart in ("script", "speech") else 1)
    assert len(animator.calls) == 2
    assert animator.calls[-1].generation_mode is GenerationMode.PRO
    assert animator.calls[-1].animator_model is AnimatorModel.OPUS_FAST
    assert animator.calls[-1].existing_project is None
    assert animator.calls[-1].regeneration_key
    assert animator.calls[-1].regeneration_key != animator.calls[0].regeneration_key
    if restart == "script":
        assert board.calls[-1].generation_mode is GenerationMode.PRO
    if restart in ("script", "speech"):
        assert saved.content.alignment.alignment_key != before.content.alignment.alignment_key
    else:
        assert saved.content.storyboard == before.content.storyboard
        assert saved.content.alignment == before.content.alignment
    assert all(artifacts.objects[key] == value for key, value in old_audio.items())
    assert before.content.playback_version() in saved.content.previous_versions


def test_regenerate_entire_lesson_runs_from_outline(video_pipeline, standalone):
    video, repo, board, _, animator, _, result = video_pipeline
    _, _, agent, planner, _ = standalone
    before = repo.require_by_id(LessonId(result.id))
    updated = GenerateAutomaticLesson(planner, video).execute(
        ReviseStandaloneLessonRequest(
            result.id,
            result.owner_id,
            result.revision,
            generation_mode=GenerationMode.FAST,
        )
    )
    assert len(agent.calls) == len(board.calls) == len(animator.calls) == 2
    assert agent.calls[-1].generation_mode is GenerationMode.FAST
    saved = repo.require_by_id(LessonId(result.id))
    assert saved.revision == updated.revision
    assert before.content.playback_version() in saved.content.previous_versions


def test_regenerated_script_invalidates_all_downstream_media(video_pipeline, standalone):
    from app.courses.application.standalone import ApproveStandaloneLesson
    from app.courses.application.standalone_media import GenerateStandaloneStoryboard

    _, repo, agent, _, _, _, result = video_pipeline
    _, uow, _, _, _ = standalone
    before = repo.require_by_id(LessonId(result.id))
    script = GenerateStandaloneScript(
        ApproveStandaloneLesson(repo, uow), GenerateStandaloneStoryboard(repo, uow, agent)
    )
    updated = script.execute(
        ReviseStandaloneLessonRequest(
            result.id,
            result.owner_id,
            result.revision,
            regenerate_from="script",
        )
    )
    saved = repo.require_by_id(LessonId(result.id))
    assert saved.content.plan == before.content.plan
    assert saved.content.storyboard is not None
    assert saved.content.alignment is saved.content.animation is saved.content.video_url is None
    assert updated.playback_content is not None


def test_failed_regeneration_preserves_finished_lesson(video_pipeline):
    video, repo, board, _, _, _, result = video_pipeline
    before = repo.require_by_id(LessonId(result.id))
    board.error = StoryboardGenerationUnavailable("Offline failure")
    with pytest.raises(StoryboardGenerationUnavailable):
        video.execute(
            ReviseStandaloneLessonRequest(
                result.id, result.owner_id, result.revision, regenerate_from="script"
            )
        )
    assert repo.require_by_id(LessonId(result.id)) == before


@pytest.mark.parametrize("invalid", ["stale", "owner"])
def test_regeneration_checks_revision_and_owner_before_generation(video_pipeline, invalid):
    video, _, board, speech, animator, _, result = video_pipeline
    counts = (len(board.calls), len(speech.calls), len(animator.calls))
    request = ReviseStandaloneLessonRequest(
        result.id, result.owner_id, result.revision, regenerate_from="script"
    )
    request = (
        replace(request, expected_revision=0)
        if invalid == "stale"
        else replace(request, owner_id="user_00000000-0000-0000-0000-000000000002")
    )
    with pytest.raises(CourseConflict if invalid == "stale" else CourseNotFound):
        video.execute(request)
    assert (len(board.calls), len(speech.calls), len(animator.calls)) == counts


@pytest.mark.parametrize(
    "title,description,expected_title,expected_description",
    [
        ("Bonds", "", "Bonds", "Bonds"),
        ("", "Explain bonds\nFor beginners", "Explain bonds", "Explain bonds\nFor beginners"),
        (" ", "x" * 2000, "x" * 120, "x" * 2000),
    ],
)
def test_missing_details_are_inferred_on_create_and_update(
    standalone, title, description, expected_title, expected_description
):
    repo, uow, agent, planner, existing = standalone
    created = CreateStandaloneLesson(repo, uow, SequenceIds()).execute(
        CreateStandaloneLessonRequest(
            existing.owner_id,
            title,
            description,
            3,
        )
    )
    assert (created.content.title, created.description) == (expected_title, expected_description)
    updated = UpdateStandaloneLesson(repo, uow).execute(
        UpdateStandaloneLessonRequest(
            created.id,
            created.owner_id,
            created.revision,
            title,
            description,
            3,
        )
    )
    planned = planner.execute(
        ReviseStandaloneLessonRequest(updated.id, updated.owner_id, updated.revision)
    )
    assert (planned.content.title, planned.description) == (expected_title, expected_description)
    assert agent.calls[-1].description == expected_description
    assert repo.require_by_id(LessonId(created.id)).description == expected_description


def test_empty_lesson_context_is_rejected_without_generation(standalone):
    repo, uow, agent, _, created = standalone
    with pytest.raises(CourseError, match="title or describe"):
        CreateStandaloneLesson(repo, uow, SequenceIds()).execute(
            CreateStandaloneLessonRequest(created.owner_id)
        )
    assert not agent.calls


@pytest.mark.parametrize(
    "field,value,keeps_script",
    [("requested_voice_id", "new-voice", True), ("visual_style_id", "whiteboard", False)],
)
def test_details_style_changes_keep_outline_and_only_invalidate_dependents(
    completed_standalone, standalone, field, value, keeps_script
):
    repo, before = completed_standalone
    _, uow, _, _, _ = standalone
    # A resolved starting style represents an already-generated lesson.
    before = replace(before, content=replace(before.content, style=LessonStyle()))
    repo.save(before)
    style = replace(before.content.style, **{field: value})
    response = UpdateStandaloneLesson(repo, uow).execute(
        UpdateStandaloneLessonRequest(
            str(before.content.id),
            str(before.owner_id),
            before.revision,
            before.content.title,
            before.description,
            before.content.minutes,
            style_input(style),
        )
    )
    saved = repo.require_by_id(before.content.id)
    assert saved.content.plan == before.content.plan
    assert saved.approved
    assert (saved.content.storyboard is not None) is keeps_script
    assert saved.content.alignment is saved.content.animation is None
    assert response.playback_content is not None


def test_failed_narration_regeneration_preserves_previous_playback_and_audio(video_pipeline):
    from app.courses.ports.speech import SpeechUnavailable

    video, repo, _, speech, _, artifacts, result = video_pipeline
    before = repo.require_by_id(LessonId(result.id))
    old_audio = {
        s.audio_key: artifacts.objects[s.audio_key] for s in before.content.alignment.scenes
    }
    speech.fail_on_call = len(speech.calls) + 1
    with pytest.raises(SpeechUnavailable):
        video.execute(
            ReviseStandaloneLessonRequest(
                result.id,
                result.owner_id,
                result.revision,
                regenerate_from="speech",
            )
        )
    assert repo.require_by_id(LessonId(result.id)) == before
    assert all(artifacts.objects[key] == value for key, value in old_audio.items())


def test_explicit_animator_session_continues_instead_of_reusing_finished_source(
    video_pipeline,
    standalone,
):
    from app.courses.application.standalone_media import GenerateStandaloneAnimation

    _, repo, _, _, animator, artifacts, result = video_pipeline
    _, uow, _, _, _ = standalone
    before = repo.require_by_id(LessonId(result.id))
    session_id = "agent_00000000-0000-0000-0000-000000000001"
    service = GenerateStandaloneAnimation(repo, uow, animator, artifacts)
    service.execute(
        ReviseStandaloneLessonRequest(
            result.id,
            result.owner_id,
            result.revision,
            message="Enlarge the labels",
            session_id=session_id,
        )
    )
    assert len(animator.calls) == 2
    continued = animator.calls[-1]
    assert continued.session.session_id == session_id
    assert continued.existing_project is None
    assert continued.previous_project_key == before.content.animation.project_key
    assert continued.visual_feedback == "Enlarge the labels"
