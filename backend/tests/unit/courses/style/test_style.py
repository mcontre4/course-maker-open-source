from dataclasses import replace

import pytest
from fakes.animator import RecordingAnimator
from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fakes.storyboard_agent import RecordingStoryboardAgent
from fakes.style import FixedVoiceCatalog, RecordingStylePlanner
from fixtures.syllabus import LESSON_ID

from app.courses.application.generate_animation import GenerateAnimationRequest
from app.courses.application.generate_speech import GenerateSpeechRequest
from app.courses.application.generate_storyboard import GenerateStoryboardRequest
from app.courses.application.standalone import ApproveStandaloneLesson
from app.courses.application.standalone_dto import ReviseStandaloneLessonRequest
from app.courses.application.standalone_media import (
    GenerateStandaloneAnimation,
    GenerateStandaloneSpeech,
    GenerateStandaloneStoryboard,
)
from app.courses.application.style import ListVoices, UpdateCourseStyle, UpdateStandaloneStyle
from app.courses.application.style_dto import ListVoicesRequest, StyleInput, UpdateStyleRequest
from app.courses.application.style_resolution import requested_style, resolve_style
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.speech import SpeechSettings
from app.courses.domain.style import LessonStyle
from app.courses.ports.style import StyleUnavailable, VoiceOption


@pytest.mark.parametrize(
    "fields",
    [
        {"request": "x" * 2001},
        {"audience": "x" * 2001},
        {"summary": ""},
        {"visuals": "x" * 1001},
        {"version": 0},
        {"version": 1001},
        {"delivery": "[excited]"},
        {"delivery": "x\ny"},
        {"delivery": "x" * 201},
        {"voice_id": "bad/voice"},
        {"accent": ""},
        {"accent": "American[shout]"},
        {"tone": "[excited]"},
        {"tone": "x" * 101},
        {"requested_pacing": "instant"},
    ],
)
def test_invalid_style_is_rejected(fields):
    with pytest.raises(CourseError):
        LessonStyle(**fields)


def test_resolver_preserves_user_input_and_validates_explicit_voice():
    planner, voices = RecordingStylePlanner(), FixedVoiceCatalog()
    result = resolve_style(
        "Explain rainbows playfully",
        StyleInput("Warm", "Experts", "steady"),
        GenerationMode.FAST,
        planner,
        voices,
    )
    assert result.request == "Warm" and result.audience == "Experts"
    assert result.voice_id == "steady" and result.voice_name == "Steady narrator"
    assert planner.calls[0][0] == "Explain rainbows playfully"
    assert [voice.id for voice in planner.calls[0][3]] == ["steady"]
    assert planner.calls[0][-1] is GenerationMode.FAST
    with pytest.raises(CourseError, match="available narrator"):
        resolve_style(
            "Topic", StyleInput(voice_id="invented"), GenerationMode.FAST, planner, voices
        )
    assert len(planner.calls) == 1


def test_voice_only_changes_do_not_call_planner_again():
    planner, voices = RecordingStylePlanner(), FixedVoiceCatalog()
    previous = LessonStyle(request="Warm", voice_id="friendly")
    result = resolve_style(
        "Topic",
        StyleInput("Warm", voice_id="steady"),
        GenerationMode.FAST,
        planner,
        voices,
        previous,
    )
    assert not planner.calls and result.version == 2
    assert result.voice_id == "steady" and result.writing == previous.writing
    assert result.change_scope(previous) == "voice"


def test_returning_to_automatic_voice_recommends_again():
    planner, voices = RecordingStylePlanner(), FixedVoiceCatalog()
    previous = LessonStyle(request="Warm", voice_id="steady", requested_voice_id="steady")
    result = resolve_style(
        "Topic", StyleInput("Warm"), GenerationMode.FAST, planner, voices, previous
    )
    assert len(planner.calls) == 1
    assert result.voice_id == "friendly" and result.requested_voice_id == ""


def test_default_legacy_and_catalog_search_paths():
    assert resolve_style("Topic", None, GenerationMode.FAST, None, None) is None
    style = resolve_style("Topic", StyleInput("Warm"), GenerationMode.FAST, None, None)
    assert style.request == "Warm"
    assert not requested_style(None).resolved
    assert (
        ListVoices(FixedVoiceCatalog()).execute(ListVoicesRequest("calm")).items[0].id == "steady"
    )


@pytest.mark.parametrize(
    "styled_lesson",
    [
        "flat-vector-science",
        "watercolor-wash",
        "tech-glow",
        "whiteboard",
        "halftone-pop",
        "risograph",
        "gouache-poster",
        "soft-3d",
        "memphis",
        "bauhaus",
        "swiss-grid",
    ],
    indirect=True,
)
def test_one_minute_style_reaches_every_stage_and_narration_cache(styled_lesson):
    repo, uow, created, styles, voices, agent, planner = styled_lesson
    request = ReviseStandaloneLessonRequest(
        created.id, created.owner_id, 0, generation_mode=GenerationMode.FAST
    )
    planned = planner.execute(request)
    assert len(styles.calls) == 1
    assert agent.calls[0].guide.style.startswith(styles.result.summary)
    assert planned.content.style.request in agent.calls[0].guide.style
    assert planned.content.style.resolved
    approved = ApproveStandaloneLesson(repo, uow).execute(
        replace(request, expected_revision=planned.revision)
    )
    boards = RecordingStoryboardAgent(uow)
    board = GenerateStandaloneStoryboard(repo, uow, boards).execute(
        replace(request, expected_revision=approved.revision)
    )
    assert planned.content.style.visuals in boards.calls[0].visual_style
    assert boards.calls[0].visual_style_id == planned.content.style.visual_style_id
    assert boards.calls[0].visual_style_version == planned.content.style.visual_style_version
    synth, artifacts = RecordingSpeech(uow), InMemorySpeechArtifacts(uow)
    speech = GenerateStandaloneSpeech(repo, uow, synth, artifacts, SpeechSettings("default"))
    voiced = speech.execute(replace(request, expected_revision=board.revision))
    assert all(
        settings.voice_id == "friendly"
        and settings.delivery == "Warm, curious, encouraging; American accent"
        for _, settings in synth.calls
    )
    speech.execute(replace(request, expected_revision=voiced.revision))
    assert len(synth.calls) == len(board.content.storyboard.scenes)
    animator = RecordingAnimator(uow)
    result = GenerateStandaloneAnimation(repo, uow, animator, artifacts).execute(
        replace(request, expected_revision=voiced.revision)
    )
    assert animator.calls[0].guide.style.startswith(styles.result.summary)
    assert animator.calls[0].visual_style_id == boards.calls[0].visual_style_id
    assert animator.calls[0].visual_style_version == boards.calls[0].visual_style_version
    assert result.content.animation is not None
    # Re-selecting a narrator keeps the approved plan and script, archives media, resets timing.
    before = repo.require_by_id(LessonId(created.id))
    update = UpdateStandaloneStyle(repo, uow, styles, voices)
    changed = update.execute(
        UpdateStyleRequest(
            created.id,
            StyleInput(
                "Playful but clear",
                "Children aged 8–10",
                "steady",
                visual_style_id=planned.content.style.visual_style_id,
            ),
            1,
            owner_id=created.owner_id,
        )
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert changed.approved and saved.content.plan == before.content.plan
    assert saved.content.storyboard == before.content.storyboard
    assert saved.content.alignment is None and saved.content.animation is None
    assert saved.content.previous_versions[-1].animation == before.content.animation
    assert changed.content.style_history[0].voice_id == "friendly"
    assert len(styles.calls) == 1


def test_style_failures_and_concurrent_changes_preserve_saved_draft(styled_lesson):
    repo, uow, created, styles, voices, _, planner = styled_lesson
    styles.error = StyleUnavailable("offline")
    with pytest.raises(StyleUnavailable):
        planner.execute(ReviseStandaloneLessonRequest(created.id, created.owner_id, 0))
    assert repo.require_by_id(LessonId(created.id)).content.plan is None
    assert not repo.require_by_id(LessonId(created.id)).content.style.resolved
    styles.error = None
    service = UpdateStandaloneStyle(repo, uow, styles, voices)
    request = UpdateStyleRequest(created.id, StyleInput("New"), 1, owner_id=created.owner_id)
    with pytest.raises(CourseConflict):
        service.execute(replace(request, expected_version=99))
    with pytest.raises(CourseNotFound):
        service.execute(replace(request, owner_id="user_00000000-0000-0000-0000-000000000002"))

    def change():
        current = repo.require_by_id(LessonId(created.id))
        repo.save(replace(current, revision=current.revision + 1))

    styles.during_run = change
    with pytest.raises(CourseConflict):
        service.execute(request)
    assert repo.require_by_id(LessonId(created.id)).content.style.request == "Playful but clear"


def test_course_inheritance_override_and_reset(animation_generation):
    _, repo, _, _, uow, before = animation_generation
    old = LessonStyle(request="Original")
    repo.save(replace(before, style=old))
    planner, voices = RecordingStylePlanner(uow), FixedVoiceCatalog()
    service = UpdateCourseStyle(repo, uow, planner, voices)
    override = service.execute(
        UpdateStyleRequest(str(before.id), StyleInput("Warm"), 0, lesson_id=LESSON_ID)
    )
    assert override.chapters[0].lessons[0].style.request == "Warm"
    assert repo.require_by_id(before.id).lesson(LESSON_ID).plan is not None
    # Course changes leave explicitly overridden lessons intact.
    content = repo.require_by_id(before.id).lesson(LESSON_ID)
    service.execute(UpdateStyleRequest(str(before.id), StyleInput("Professional"), 1))
    assert repo.require_by_id(before.id).lesson(LESSON_ID) == content
    reset = service.execute(UpdateStyleRequest(str(before.id), None, 1, lesson_id=LESSON_ID))
    assert reset.chapters[0].lessons[0].style is None
    assert reset.style.request == "Professional"
    with pytest.raises(CourseConflict):
        service.execute(UpdateStyleRequest(str(before.id), StyleInput("Other"), 1))


def test_applying_first_course_style_invalidates_existing_unstyled_lessons(animation_generation):
    _, repo, _, _, uow, course = animation_generation
    service = UpdateCourseStyle(repo, uow, RecordingStylePlanner(uow), FixedVoiceCatalog())
    original = course.lesson(LESSON_ID)
    service.execute(UpdateStyleRequest(str(course.id), StyleInput("Playful"), 0))
    saved = repo.require_by_id(course.id).lesson(LESSON_ID)
    assert saved.plan is None and saved.storyboard is None and saved.alignment is None
    assert saved.previous_versions[0].alignment == original.alignment


def test_voice_override_reuses_inherited_style_without_replanning(animation_generation):
    _, repo, _, _, uow, course = animation_generation
    inherited = LessonStyle(request="Professional", voice_id="friendly", version=8)
    repo.save(replace(course, style=inherited))
    planner = RecordingStylePlanner(uow)
    service = UpdateCourseStyle(repo, uow, planner, FixedVoiceCatalog())
    original = course.lesson(LESSON_ID)
    service.execute(
        UpdateStyleRequest(
            str(course.id),
            StyleInput("Professional", voice_id="steady"),
            0,
            lesson_id=LESSON_ID,
        )
    )
    saved = repo.require_by_id(course.id).lesson(LESSON_ID)
    assert not planner.calls
    assert saved.style.version == 1 and saved.style.voice_id == "steady"
    assert saved.plan == original.plan and saved.storyboard == original.storyboard
    assert saved.alignment is None


@pytest.mark.parametrize(
    "field,scope",
    [
        ("writing", "content"),
        ("audience", "content"),
        ("visuals", "visuals"),
        ("motion", "visuals"),
        ("delivery", "voice"),
        ("summary", "none"),
    ],
)
def test_invalidation_scope_and_history(animation_generation, field, scope):
    _, repo, _, _, _, before = animation_generation
    original = before.lesson(LESSON_ID)
    old = LessonStyle()
    lesson = replace(original, style=old)
    changed = lesson.restyle(replace(old, **{field: "Changed"}))
    assert changed.plan is None if scope == "content" else changed.plan == original.plan
    assert (
        changed.storyboard is None
        if scope in ("content", "visuals")
        else changed.storyboard == original.storyboard
    )
    assert changed.alignment is None if scope != "none" else changed.alignment == original.alignment
    assert changed.previous_versions[-1].alignment == original.alignment
    assert not changed.previous_versions[-1].previous_versions
    if scope == "none":
        with pytest.raises(CourseError, match="history limit"):
            replace(lesson, previous_versions=(lesson,) * 50).restyle(old)


@pytest.mark.parametrize(
    "visual_style_id",
    [
        "flat-vector-science",
        "watercolor-wash",
        "tech-glow",
        "whiteboard",
        "halftone-pop",
        "risograph",
        "gouache-poster",
        "soft-3d",
        "memphis",
        "bauhaus",
        "swiss-grid",
    ],
)
@pytest.mark.parametrize("lesson_override", [False, True])
def test_course_style_is_used_by_storyboard_speech_and_animation(
    animation_generation, storyboard_generation, speech_generation, visual_style_id, lesson_override
):
    animation, repo, animator, _, _, course = animation_generation
    style = LessonStyle(voice_id="steady", delivery="Calm, warm", visual_style_id=visual_style_id)
    course = replace(course, style=LessonStyle() if lesson_override else style)
    if lesson_override:
        course = course._replace_lesson(replace(course.lesson(LESSON_ID), style=style))
    repo.save(course)
    animation.execute(GenerateAnimationRequest(str(course.id), LESSON_ID, "Legacy request"))
    assert style.visuals in animator.calls[-1].visual_style
    assert animator.calls[-1].visual_style_id == visual_style_id
    # Other fixtures share this same repository; clear downstream content to exercise all stages.
    lesson = repo.require_by_id(course.id).lesson(LESSON_ID)
    clean = replace(
        lesson, storyboard=None, storyboard_generation=None, alignment=None, animation=None
    )
    repo.save(course._replace_lesson(clean))
    boards, _, agent, _, _, _ = storyboard_generation
    boards.execute(GenerateStoryboardRequest(str(course.id), LESSON_ID))
    assert style.visuals in agent.calls[-1].visual_style
    assert agent.calls[-1].visual_style_id == visual_style_id
    assert agent.calls[-1].visual_style_version == style.visual_style_version
    speech, _, synth, _, _, _, _ = speech_generation
    speech.execute(GenerateSpeechRequest(str(course.id), LESSON_ID))
    assert synth.calls[-1][1].voice_id == "steady"


def test_existing_neutral_speech_manifest_remains_reusable(speech_generation):
    import json

    speech, _, synthesizer, artifacts, _, course, _ = speech_generation
    generated = speech.execute(GenerateSpeechRequest(str(course.id), LESSON_ID))
    alignment = generated.chapters[0].lessons[0].alignment
    key = alignment.alignment_key
    manifest = json.loads(artifacts.objects[key])
    del manifest["settings"]["delivery"]
    artifacts.objects[key] = json.dumps(manifest).encode()
    count = len(synthesizer.calls)
    cached = speech.execute(GenerateSpeechRequest(str(course.id), LESSON_ID))
    assert cached == generated and len(synthesizer.calls) == count


def test_draft_style_changes_remain_pending_until_outline_planning(styled_lesson):
    from app.courses.application.standalone import UpdateStandaloneLesson
    from app.courses.application.standalone_dto import UpdateStandaloneLessonRequest

    repo, uow, created, styles, voices, agent, planner = styled_lesson
    request = UpdateStandaloneLessonRequest(
        created.id,
        created.owner_id,
        created.revision,
        created.content.title,
        created.description,
        created.content.minutes,
        StyleInput("Warm and reassuring", "Beginners"),
    )
    service = UpdateStandaloneLesson(repo, uow)
    updated = service.execute(request)
    assert updated.content.style.request == "Warm and reassuring"
    assert not updated.content.style.resolved
    assert updated.content.style.version == 2
    assert styles.calls == []
    same = service.execute(replace(request, expected_revision=updated.revision))
    assert same.revision == updated.revision
    planner.execute(ReviseStandaloneLessonRequest(created.id, created.owner_id, same.revision))
    assert styles.calls[0][1:3] == ("Warm and reassuring", "Beginners")


@pytest.mark.parametrize("context_changed", [False, True])
def test_draft_context_changes_replan_only_resolved_profiles(context_changed):
    from app.courses.application.style_resolution import draft_style

    assert draft_style(None, None, context_changed) is None
    pending = requested_style(StyleInput("Playful", "Children"))
    assert draft_style(None, pending, context_changed) == pending
    resolved = replace(pending, resolved=True)
    updated = draft_style(None, resolved, context_changed)
    assert updated.resolved is not context_changed
    assert updated.version == resolved.version + int(context_changed)


def test_unspecified_style_selects_only_american_candidates():
    planner, catalog = RecordingStylePlanner(), FixedVoiceCatalog()
    british = VoiceOption("british", "British", labels=("accent: British",))
    catalog.items = (british, *catalog.items)
    planner.result = replace(planner.result, voice_id="british")
    result = resolve_style("Physics for beginners", None, GenerationMode.FAST, planner, catalog)
    assert result.accent == "American" and result.voice_id == "friendly"
    assert all(v.id != "british" for v in planner.calls[0][3])
    assert planner.preferences == {"accent": "American", "tone": "", "pacing": ""}


def test_explicit_accent_and_custom_tone_reach_planning_and_speech():
    planner, catalog = RecordingStylePlanner(), FixedVoiceCatalog()
    catalog.items += (VoiceOption("british", "British", labels=("accent: british",)),)
    result = resolve_style(
        "Physics for beginners",
        StyleInput(accent="British", tone="Reassuring and curious", pacing="Relaxed"),
        GenerationMode.FAST,
        planner,
        catalog,
    )
    assert result.voice_id == "british" and result.pacing == "Relaxed"
    assert result.speech_delivery() == "Reassuring and curious; British accent; relaxed pacing"
    assert planner.preferences["tone"] == "Reassuring and curious"
    assert planner.preferences["accent"] == "British"
    assert [v.id for v in planner.calls[0][3]] == ["british"]
    with pytest.raises(CourseError, match="matching the selected accent"):
        resolve_style(
            "Topic",
            StyleInput(voice_id="friendly", accent="British"),
            GenerationMode.FAST,
            planner,
            catalog,
        )


@pytest.mark.parametrize(
    "labels",
    [("accent: British",), (), ("catalog_permission_required", "accent: British")],
)
def test_missing_matching_voice_never_silently_changes_accent(labels):
    catalog = FixedVoiceCatalog()
    catalog.items = (VoiceOption("unmatched", "Unmatched", labels=labels),)
    with pytest.raises(StyleUnavailable, match="No verified American"):
        resolve_style("Topic", None, GenerationMode.FAST, RecordingStylePlanner(), catalog)


@pytest.mark.parametrize("accent", ["American", "British"])
def test_speech_only_key_uses_configured_narrator_with_unverified_accent_notice(accent):
    catalog = FixedVoiceCatalog()
    catalog.items = (
        VoiceOption("configured", "Configured narrator", labels=("catalog_permission_required",)),
    )
    planner = RecordingStylePlanner()
    result = resolve_style(
        "Topic", StyleInput(accent=accent), GenerationMode.FAST, planner, catalog
    )
    assert result.voice_id == "configured"
    assert result.accent == accent
    assert f"requested {accent} accent cannot be verified" in result.voice_notice
    assert "voices_read" in result.voice_notice
    assert planner.calls[0][3] == catalog.items


def test_outline_is_saved_when_voice_browsing_permission_is_missing(styled_lesson):
    repo, _, created, _, voices, _, planner = styled_lesson
    voices.items = (
        VoiceOption("configured", "Configured narrator", labels=("catalog_permission_required",)),
    )
    planned = planner.execute(ReviseStandaloneLessonRequest(created.id, created.owner_id, 0))
    saved = repo.require_by_id(LessonId(created.id))
    assert saved.content.plan is not None
    assert planned.content.style.voice_id == saved.content.style.voice_id == "configured"
    assert "American accent cannot be verified" in saved.content.style.voice_notice


def test_tone_change_keeps_content_and_visuals_and_invalidates_voice_only():
    previous = LessonStyle(request="Warm", voice_id="friendly", writing="Keep this script")
    planner = RecordingStylePlanner()
    planner.result = replace(planner.result, writing="Unwanted rewrite", visuals="Unwanted visuals")
    result = resolve_style(
        "Topic",
        StyleInput("Warm", tone="Calm"),
        GenerationMode.FAST,
        planner,
        FixedVoiceCatalog(),
        previous,
    )
    assert result.writing == previous.writing and result.visuals == previous.visuals
    assert result.change_scope(previous) == "voice"
    assert result.speech_delivery() == "Calm; American accent"


def test_advanced_preferences_survive_draft_updates_and_outline_planning(styled_lesson):
    from app.courses.application.standalone import UpdateStandaloneLesson
    from app.courses.application.standalone_dto import UpdateStandaloneLessonRequest
    from app.courses.application.style_dto import style_input

    repo, uow, created, styles, _, _, planner = styled_lesson
    preferences = StyleInput("Warm", "Beginners", accent="American", tone="Calm", pacing="Relaxed")
    updated = UpdateStandaloneLesson(repo, uow).execute(
        UpdateStandaloneLessonRequest(
            created.id,
            created.owner_id,
            created.revision,
            created.content.title,
            created.description,
            created.content.minutes,
            preferences,
        )
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert style_input(saved.content.style) == preferences
    planned = planner.execute(
        ReviseStandaloneLessonRequest(created.id, created.owner_id, updated.revision)
    )
    saved = repo.require_by_id(LessonId(created.id))
    assert style_input(saved.content.style) == preferences
    assert planned.content.style.tone == "Calm"
    assert styles.preferences == {"accent": "American", "tone": "Calm", "pacing": "Relaxed"}


def test_long_inferred_delivery_stays_within_provider_limit():
    result = LessonStyle(delivery="x" * 200, accent="American", requested_pacing="Relaxed")
    assert len(result.speech_delivery()) <= 200
    assert result.speech_delivery().endswith("American accent; relaxed pacing")
