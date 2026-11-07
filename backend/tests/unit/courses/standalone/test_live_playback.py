from dataclasses import replace

import pytest
from fakes.courses import RecordingUnitOfWork
from fakes.lesson_playback import ProgressiveAnimator, RecordingLessonPlayback

from app.courses.application.lesson_playback import (
    GetStandaloneLessonPlayback,
    GetStandaloneLessonPlaybackRequest,
)
from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
from app.courses.application.standalone_media import GenerateStandaloneAnimation
from app.courses.domain.animation import AnimationProject
from app.courses.domain.errors import ContentNotReady, CourseConflict, CourseNotFound
from app.courses.ports.animator import AnimationUnavailable

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"


def test_code_is_persisted_and_playable_before_delivery_finishes(voiced_standalone):
    _, repo, _, artifacts, before = voiced_standalone
    uow = RecordingUnitOfWork(repo)
    playback = RecordingLessonPlayback(uow)
    reader = GetStandaloneLessonPlayback(repo, playback, uow)

    def during_delivery(project):
        assert uow.exited
        saved = repo.require_by_id(before.content.id)
        assert saved.content.animation == project
        assert not saved.content.is_published
        assert saved.content.alignment == before.content.alignment
        result = reader.execute(GetStandaloneLessonPlaybackRequest(str(before.content.id), OWNER))
        assert not result.video_ready
        assert result.source_hash == project.output_hash

    response = GenerateStandaloneAnimation(
        repo, uow, ProgressiveAnimator(during_delivery), artifacts
    ).execute(ReviseStandaloneLessonRequest(str(before.content.id), OWNER, before.revision))
    saved = repo.require_by_id(before.content.id)
    assert saved.content.animation.review_status == "skipped"
    assert saved.content.is_published
    assert response.revision == before.revision + 2


def test_failed_delivery_retains_preview_and_retry_reuses_its_source(voiced_standalone):
    _, repo, _, artifacts, before = voiced_standalone
    uow = RecordingUnitOfWork(repo)
    animator = ProgressiveAnimator(lambda project: None)
    animator.error = AnimationUnavailable("Encoder failed")
    service = GenerateStandaloneAnimation(repo, uow, animator, artifacts)
    with pytest.raises(AnimationUnavailable, match="Encoder failed"):
        service.execute(
            ReviseStandaloneLessonRequest(str(before.content.id), OWNER, before.revision)
        )
    pending = repo.require_by_id(before.content.id)
    assert pending.content.animation.review_status == "pending"
    animator.error = None
    service.execute(ReviseStandaloneLessonRequest(str(before.content.id), OWNER, pending.revision))
    assert animator.inputs[-1].existing_project == pending.content.animation
    assert repo.require_by_id(before.content.id).content.animation.review_status == "skipped"


def test_concurrent_edit_is_not_overwritten_by_background_delivery(voiced_standalone):
    _, repo, _, artifacts, before = voiced_standalone
    uow = RecordingUnitOfWork(repo)

    def edit(project):
        saved = repo.require_by_id(before.content.id)
        repo.save(replace(saved, revision=saved.revision + 1, description="Concurrent change"))

    with pytest.raises(CourseConflict, match="changed during generation"):
        GenerateStandaloneAnimation(repo, uow, ProgressiveAnimator(edit), artifacts).execute(
            ReviseStandaloneLessonRequest(str(before.content.id), OWNER, before.revision)
        )
    assert repo.require_by_id(before.content.id).description == "Concurrent change"


def test_preview_checks_owner_and_source_version_before_reading_assets(voiced_standalone):
    _, repo, _, _, before = voiced_standalone
    project = AnimationProject(
        str(before.content.id),
        "a" * 64,
        "a" * 64 + "/javascript",
        "b" * 64,
        "test",
        before.content.alignment.duration_sec,
        review_status="pending",
    )
    repo.save(replace(before, content=replace(before.content, animation=project)))
    uow = RecordingUnitOfWork(repo)
    playback = RecordingLessonPlayback(uow)
    service = GetStandaloneLessonPlayback(repo, playback, uow)
    with pytest.raises(CourseNotFound):
        service.execute(GetStandaloneLessonPlaybackRequest(str(before.content.id), OTHER, True))
    with pytest.raises(ContentNotReady, match="changed"):
        service.execute(
            GetStandaloneLessonPlaybackRequest(str(before.content.id), OWNER, True, "c" * 64)
        )
    assert not playback.calls
    preview = service.execute(
        GetStandaloneLessonPlaybackRequest(str(before.content.id), OWNER, True, project.output_hash)
    )
    assert preview.preview_html == "<html>code preview</html>"
    playback.ready = True
    assert service.execute(
        GetStandaloneLessonPlaybackRequest(str(before.content.id), OWNER)
    ).video_ready
