from dataclasses import replace

import pytest
from fakes.courses import RecordingUnitOfWork
from fakes.lesson_playback import RecordingLessonPlayback
from fakes.lesson_video import RecordingLessonVideo

from app.courses.application.lesson_playback import (
    GetStandaloneLessonPlayback,
    GetStandaloneLessonPlaybackRequest,
)
from app.courses.application.lesson_video import (
    GetStandaloneLessonVideo,
    GetStandaloneLessonVideoRequest,
)
from app.courses.application.save_standalone_script import (
    SaveStandaloneScript,
    SaveStandaloneScriptRequest,
)
from app.courses.application.standalone_dto import standalone_response
from app.courses.domain.errors import ContentNotReady, CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import LessonId

OTHER_OWNER = "user_00000000-0000-0000-0000-000000000002"


def test_script_edit_persists_narration_and_keeps_the_current_video(completed_standalone):
    repo, before = completed_standalone
    uow = RecordingUnitOfWork(repo)
    narrations = tuple(
        scene.narration_text + " Share electrons." for scene in before.content.storyboard.scenes
    )
    result = SaveStandaloneScript(repo, uow).execute(
        SaveStandaloneScriptRequest(
            str(before.content.id), str(before.owner_id), before.revision, narrations
        )
    )
    saved = repo.require_by_id(before.content.id)
    assert tuple(s.narration_text for s in saved.content.storyboard.scenes) == narrations
    assert saved.content.plan == before.content.plan
    assert saved.content.alignment is None
    assert saved.content.animation is None
    assert result.playback_content.animation.output_hash == before.content.animation.output_hash
    assert saved.content.previous_versions == (replace(before.content, previous_versions=()),)
    assert uow.commits == 1
    videos = RecordingLessonVideo(uow)
    response = GetStandaloneLessonVideo(repo, videos, uow).execute(
        GetStandaloneLessonVideoRequest(str(before.content.id), str(before.owner_id))
    )
    assert response.content == b"saved-video"
    assert videos.animations == [before.content.animation]


def test_script_noop_and_invalid_edits_never_invalidate_saved_media(completed_standalone):
    repo, before = completed_standalone
    uow = RecordingUnitOfWork(repo)
    service = SaveStandaloneScript(repo, uow)
    request = SaveStandaloneScriptRequest(
        str(before.content.id),
        str(before.owner_id),
        before.revision,
        tuple(s.narration_text for s in before.content.storyboard.scenes),
    )
    assert service.execute(request).revision == before.revision
    for invalid in ((), ("",) * len(request.narrations)):
        with pytest.raises(CourseError):
            service.execute(replace(request, narrations=invalid))
    with pytest.raises(CourseConflict):
        service.execute(replace(request, expected_revision=before.revision - 1))
    with pytest.raises(CourseNotFound):
        service.execute(replace(request, owner_id=OTHER_OWNER))
    assert repo.require_by_id(before.content.id) == before


def test_reanchors_a_long_repeated_passage_without_exceeding_the_cue_limit(completed_standalone):
    _, before = completed_standalone
    scene = before.content.storyboard.scenes[0]
    narration = "rain " * 200 + "One cloud finally releases a drop."
    revised = scene.with_narration(narration)
    assert revised.narration_text == narration
    assert all(len(cue.anchor_text) <= 500 for cue in revised.cues)
    assert all(narration.count(cue.anchor_text) == 1 for cue in revised.cues)
    with pytest.raises(CourseError, match="more varied narration"):
        scene.with_narration("rain " * 200)


def test_script_requires_an_existing_script(standalone):
    repo, uow, _, _, created = standalone
    with pytest.raises(CourseConflict, match="Generate the script"):
        SaveStandaloneScript(repo, uow).execute(
            SaveStandaloneScriptRequest(created.id, created.owner_id, created.revision, ("Hello",))
        )
    assert repo.require_by_id(LessonId(created.id)).revision == created.revision


def test_old_video_remains_available_during_render_and_new_video_replaces_it(completed_standalone):
    repo, before = completed_standalone
    old = before.content.animation
    draft = before.edit_outline(replace(before.content.plan, required_facts=("A revised fact",)))
    pending = replace(old, output_hash="c" * 64, review_status="pending")
    # A generated replacement is still a preview until delivery finishes.
    content = replace(
        before.content, previous_versions=draft.content.previous_versions, animation=pending
    )
    updating = replace(before, content=content, revision=before.revision + 1)
    repo.save(updating)
    uow = RecordingUnitOfWork(repo)
    playback = RecordingLessonPlayback(uow)
    reader = GetStandaloneLessonPlayback(repo, playback, uow)
    request = GetStandaloneLessonPlaybackRequest(str(before.content.id), str(before.owner_id))
    assert reader.execute(request).source_hash == old.output_hash
    assert (
        reader.execute(replace(request, source_hash=pending.output_hash)).source_hash
        == pending.output_hash
    )
    assert standalone_response(updating).playback_content.animation.output_hash == old.output_hash
    with pytest.raises(ContentNotReady):
        reader.execute(replace(request, source_hash="d" * 64))
    completed = replace(
        updating, content=replace(content, animation=replace(pending, review_status="approved"))
    )
    repo.save(completed)
    assert reader.execute(request).source_hash == pending.output_hash
    assert (
        reader.execute(replace(request, source_hash=old.output_hash)).source_hash == old.output_hash
    )
    assert standalone_response(completed).playback_content is None


def test_brief_edits_keep_the_previous_video_and_preservation_is_idempotent(completed_standalone):
    _, before = completed_standalone
    updated = before.update_details(before.content.title, "A different audience and explanation", 3)
    assert updated.content.plan is None
    assert updated.content.playback_version() == replace(before.content, previous_versions=())
    preserved = before.content.preserve_playback()
    assert preserved.preserve_playback() == preserved
    assert updated.content.preserve_playback() == updated.content


def test_editing_a_cue_phrase_reanchors_visuals_to_the_new_narration(completed_standalone):
    repo, before = completed_standalone
    scene = before.content.storyboard.scenes[0]
    original = scene.cues[0].anchor_text
    narrations = [s.narration_text for s in before.content.storyboard.scenes]
    narrations[0] = narrations[0].replace(original, "A different spoken explanation", 1)
    updated = before.edit_script(tuple(narrations))
    changed = updated.content.storyboard.scenes[0]
    assert changed.cues[0].id == scene.cues[0].id
    for cue in changed.cues:
        first = changed.narration_text.find(cue.anchor_text)
        assert first >= 0
        assert changed.narration_text.find(cue.anchor_text, first + 1) == -1
    repetitive = scene.with_narration("rain " * 50)
    assert all(c.anchor_text in repetitive.narration_text for c in repetitive.cues)
    assert repo.require_by_id(before.content.id) == before
