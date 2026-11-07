from dataclasses import asdict, replace

import pytest
from fakes.speech import speech_result
from fixtures.speech import legacy_speech
from fixtures.syllabus import LESSON_ID

from app.courses.application.generate_speech import GenerateSpeech, GenerateSpeechRequest
from app.courses.application.generate_storyboard import artifact_hash
from app.courses.application.get_speech_artifact import GetSpeechArtifact, GetSpeechArtifactRequest
from app.courses.domain.errors import ContentNotReady, CourseConflict, CourseError, CourseNotFound
from app.courses.domain.speech import AlignmentError, SpeechSettings, TimedText, align_scene
from app.courses.ports.speech import SpeechArtifactUnavailable, SpeechUnavailable


def test_generates_measured_timeline_and_reuses_saved_audio(speech_generation):
    service, courses, provider, artifacts, uow, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    response = service.execute(request)
    saved = courses.require_by_id(before.id).lesson(LESSON_ID)
    alignment = saved.alignment
    assert alignment.status == "audio_aligned"
    assert alignment.settings.model_id == "eleven_v4"
    assert alignment.scenes[0].duration_sec != saved.storyboard.scenes[0].target_duration_sec
    first, second = alignment.scenes
    assert second.timeline_start_sec == first.duration_sec + 0.25
    assert first.cues[0].start_sec == 0
    assert first.cues[0].end_sec == len(first.cues[0].anchor_text) / 100
    assert first.transcript == saved.storyboard.scenes[0].narration_text
    assert artifacts.objects[first.audio_key].startswith(b"RIFF")
    assert alignment.alignment_key in artifacts.objects
    assert uow.commits == 1
    assert service.execute(request) == response
    assert len(provider.calls) == 2
    assert response.chapters[0].lessons[0].alignment.duration_sec == alignment.duration_sec


def test_retry_reuses_completed_scenes(speech_generation):
    service, courses, provider, artifacts, uow, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    provider.fail_on_call = 2
    with pytest.raises(SpeechUnavailable):
        service.execute(request)
    assert courses.require_by_id(before.id) == before
    assert uow.commits == 0 and len(artifacts.scenes) == 1
    provider.fail_on_call = None
    service.execute(request)
    assert len(provider.calls) == 3
    assert courses.require_by_id(before.id).lesson(LESSON_ID).alignment is not None


def test_legacy_scene_checkpoints_are_not_reused_after_delivery_fix(speech_generation):
    service, courses, provider, artifacts, _, before, settings = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    board = before.lesson(LESSON_ID).storyboard
    scenes = {scene.scene_id: scene for scene in board.scenes}
    for key, aligned in tuple(artifacts.scenes.items()):
        scene = scenes[aligned.scene_id]
        legacy_hash = artifact_hash(
            {
                "scene_id": scene.scene_id,
                "text": scene.narration_text,
                "cues": [(cue.id, cue.anchor_text) for cue in scene.cues],
                "settings": asdict(settings),
                "version": "speech-v1",
            }
        )
        del artifacts.scenes[key]
        artifacts.scenes[key.replace(aligned.input_hash, legacy_hash)] = replace(
            aligned, input_hash=legacy_hash
        )
    courses.save(before)

    service.execute(request)

    assert len(provider.calls) == 2 * len(board.scenes)
    assert courses.require_by_id(before.id).lesson(LESSON_ID).alignment is not None


def test_completed_legacy_audio_refreshes_and_invalidates_old_video(speech_generation):
    service, courses, provider, artifacts, uow, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    current = courses.require_by_id(before.id)
    older = legacy_speech(current.lesson(LESSON_ID), artifacts)
    courses.save(current._replace_lesson(replace(older, video_url="https://example.com/old.mp4")))

    service.execute(request)

    saved = courses.require_by_id(before.id).lesson(LESSON_ID)
    assert saved.alignment != older.alignment
    assert saved.storyboard == older.storyboard
    assert saved.plan == older.plan
    assert saved.video_url is None and saved.animation is None
    assert len(provider.calls) == 4
    assert uow.commits == 2
    service.execute(request)
    assert len(provider.calls) == 4


def test_failed_legacy_refresh_preserves_saved_audio(speech_generation):
    service, courses, provider, artifacts, uow, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    current = courses.require_by_id(before.id)
    older = current._replace_lesson(legacy_speech(current.lesson(LESSON_ID), artifacts))
    courses.save(older)
    provider.fail_on_call = 3

    with pytest.raises(SpeechUnavailable):
        service.execute(request)

    assert courses.require_by_id(before.id) == older
    assert uow.commits == 1


def test_reviewed_legacy_lesson_cannot_incur_refresh_charges(speech_generation):
    service, courses, provider, artifacts, _, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    current = courses.require_by_id(before.id)
    older = current._replace_lesson(legacy_speech(current.lesson(LESSON_ID), artifacts))
    courses.save(replace(older, reviewed=(LESSON_ID,)))

    with pytest.raises(CourseConflict, match="Reviewed"):
        service.execute(request)

    assert len(provider.calls) == 2


def test_storage_failure_cannot_mark_audio_ready(speech_generation):
    service, courses, _, artifacts, uow, before, _ = speech_generation
    artifacts.fail = True
    with pytest.raises(SpeechArtifactUnavailable):
        service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    assert courses.require_by_id(before.id) == before
    assert uow.commits == 0


def test_concurrent_edit_cannot_publish_stale_audio(speech_generation):
    service, courses, provider, _, uow, before, _ = speech_generation
    provider.on_call = lambda: courses.save(replace(before, title="Concurrent edit"))
    with pytest.raises(CourseConflict, match="changed"):
        service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    assert courses.require_by_id(before.id).title == "Concurrent edit"
    assert courses.require_by_id(before.id).lesson(LESSON_ID).alignment is None
    assert uow.commits == 0


@pytest.mark.parametrize("change", ["draft", "missing_storyboard", "reviewed"])
def test_preconditions_prevent_paid_requests(speech_generation, change):
    service, courses, provider, _, _, before, _ = speech_generation
    if change == "draft":
        changed = replace(before, status="draft")
    elif change == "reviewed":
        changed = replace(before, reviewed=(LESSON_ID,))
    else:
        changed = before._replace_lesson(replace(before.lesson(LESSON_ID), storyboard=None))
    courses.save(changed)
    with pytest.raises(CourseConflict):
        service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    assert not provider.calls


def test_changed_settings_require_explicit_regeneration(speech_generation):
    service, courses, provider, artifacts, uow, before, settings = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    changed = GenerateSpeech(courses, provider, artifacts, replace(settings, stability=0.8), uow)
    with pytest.raises(CourseConflict, match="different speech settings"):
        changed.execute(request)
    assert len(provider.calls) == 2


def test_corrupt_checkpoint_is_not_reused(speech_generation):
    service, courses, provider, artifacts, _, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    provider.fail_on_call = 2
    with pytest.raises(SpeechUnavailable):
        service.execute(request)
    key = next(iter(artifacts.objects))
    artifacts.objects[key] = b"corrupt"
    with pytest.raises(SpeechArtifactUnavailable, match="corrupt"):
        service.execute(request)
    assert courses.require_by_id(before.id) == before


def test_script_and_plan_changes_invalidate_audio(speech_generation):
    service, courses, _, _, _, before, _ = speech_generation
    service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    course = courses.require_by_id(before.id)
    lesson = course.lesson(LESSON_ID)
    assert lesson.revise_outline("New title", lesson.topics, lesson.minutes).alignment is None
    assert lesson.revise_outline(lesson.title, lesson.topics, lesson.minutes).alignment is not None
    assert (
        course.plan_lesson(LESSON_ID, lesson.plan, lesson.plan_generation)
        .lesson(LESSON_ID)
        .alignment
        is None
    )
    assert (
        course.storyboard_lesson(LESSON_ID, lesson.storyboard, lesson.storyboard_generation)
        .lesson(LESSON_ID)
        .alignment
        is None
    )


@pytest.mark.parametrize("change", ["missing", "reordered", "outside", "zero", "nan"])
def test_rejects_unreliable_character_timing(change):
    measured = speech_result("Hello world").measured
    characters = measured.characters
    with pytest.raises(AlignmentError):
        if change == "missing":
            replace(measured, characters=())
        elif change == "reordered":
            replace(measured, characters=tuple(reversed(characters)))
        elif change == "outside":
            replace(measured, characters=(*characters[:-1], TimedText("d", 0.1, 200)))
        elif change == "zero":
            replace(measured, characters=(TimedText("H", 0, 0), *characters[1:]))
        else:
            TimedText("H", float("nan"), 1)


def test_exact_transcript_is_required_for_cue_mapping(speech_generation):
    _, _, _, _, _, before, _ = speech_generation
    scene = before.lesson(LESSON_ID).storyboard.scenes[0]
    with pytest.raises(AlignmentError, match="verbatim"):
        align_scene(
            scene,
            speech_result(scene.narration_text.lower()).measured,
            "a" * 64,
            "audio/test.wav",
            "b" * 64,
        )


@pytest.mark.parametrize(
    "settings",
    [
        {"voice_id": "../secret"},
        {"similarity": float("inf")},
        {"stability": -0.1},
        {"model_id": "eleven_flash_v2_5"},
        {"sample_rate": 44100},
    ],
)
def test_rejects_invalid_voice_configuration(settings):
    with pytest.raises(CourseError):
        SpeechSettings(**({"voice_id": "test"} | settings))


@pytest.mark.parametrize("kind", ["audio", "transcript", "alignment"])
def test_reads_only_the_selected_lessons_published_artifacts(speech_generation, kind):
    service, courses, _, artifacts, uow, before, _ = speech_generation
    service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    reader = GetSpeechArtifact(courses, artifacts, uow)
    aligned = courses.require_by_id(before.id).lesson(LESSON_ID).alignment
    scene = aligned.scenes[0]
    response = reader.execute(
        GetSpeechArtifactRequest(str(before.id), LESSON_ID, kind, scene.scene_id)
    )
    if kind == "audio":
        assert response.content == artifacts.objects[scene.audio_key]
        assert response.content_type == "audio/wav"
    elif kind == "transcript":
        assert response.content.decode() == "\n\n".join(s.transcript for s in aligned.scenes)
        assert response.content_type == "text/plain; charset=utf-8"
    else:
        assert response.content == artifacts.objects[aligned.alignment_key]
        assert response.content_type == "application/json"


def test_unpublished_or_missing_artifacts_cannot_be_retrieved(speech_generation):
    service, courses, _, artifacts, uow, before, _ = speech_generation
    reader = GetSpeechArtifact(courses, artifacts, uow)
    request = GetSpeechArtifactRequest(str(before.id), LESSON_ID, "alignment")
    with pytest.raises(ContentNotReady):
        reader.execute(request)
    service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    with pytest.raises(CourseNotFound):
        reader.execute(replace(request, kind="audio", scene_id="unknown"))
    with pytest.raises(CourseNotFound):
        reader.execute(replace(request, kind="arbitrary/path"))
    artifacts.objects.clear()
    with pytest.raises(SpeechArtifactUnavailable):
        reader.execute(request)


@pytest.mark.parametrize("limit", ["scene", "lesson"])
def test_cost_limits_preflight_the_complete_storyboard(speech_generation, limit):
    service, courses, provider, _, _, before, _ = speech_generation
    lesson = before.lesson(LESSON_ID)
    board = lesson.storyboard
    if limit == "scene":
        scene = replace(
            board.scenes[0], narration_text=board.scenes[0].narration_text + "x" * 10000
        )
        board = replace(board, scenes=(scene, board.scenes[1]))
    else:
        narration = "Look at the name score. " + "A name refers to a value. " * 20 + "x" * 8500
        board = replace(
            board,
            scenes=tuple(
                replace(
                    board.scenes[0],
                    scene_id=f"s{i:02}",
                    narration_text=narration,
                    target_duration_sec=50,
                )
                for i in range(12)
            ),
        )
    courses.save(before._replace_lesson(replace(lesson, storyboard=board)))
    with pytest.raises(CourseConflict, match="characters"):
        service.execute(GenerateSpeechRequest(str(before.id), LESSON_ID))
    assert not provider.calls


@pytest.mark.parametrize("kind", ["audio", "transcript", "alignment", "invalid_json"])
def test_cache_and_downloads_reject_damaged_published_artifacts(speech_generation, kind):
    service, courses, provider, artifacts, uow, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    alignment = courses.require_by_id(before.id).lesson(LESSON_ID).alignment
    scene = alignment.scenes[0]
    if kind == "audio":
        key = scene.audio_key
    elif kind == "transcript":
        key = alignment.alignment_key.removesuffix("alignment.json") + "transcript.txt"
    else:
        key = alignment.alignment_key
    artifacts.objects[key] = b"\xff" if kind == "invalid_json" else b"{}"
    with pytest.raises(SpeechArtifactUnavailable, match="corrupt"):
        service.execute(request)
    reader = GetSpeechArtifact(courses, artifacts, uow)
    with pytest.raises(SpeechArtifactUnavailable, match="corrupt"):
        reader.execute(
            GetSpeechArtifactRequest(
                str(before.id),
                LESSON_ID,
                "alignment" if kind == "invalid_json" else kind,
                scene.scene_id,
            )
        )
    assert len(provider.calls) == 2


def test_cache_does_not_report_missing_audio_as_ready(speech_generation):
    service, courses, provider, artifacts, _, before, _ = speech_generation
    request = GenerateSpeechRequest(str(before.id), LESSON_ID)
    service.execute(request)
    scene = courses.require_by_id(before.id).lesson(LESSON_ID).alignment.scenes[0]
    del artifacts.objects[scene.audio_key]
    with pytest.raises(SpeechArtifactUnavailable, match="missing"):
        service.execute(request)
    assert len(provider.calls) == 2
