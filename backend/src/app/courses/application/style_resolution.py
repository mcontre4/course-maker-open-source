from contextlib import nullcontext
from dataclasses import replace

from app.courses.application.style_dto import StyleInput, style_input
from app.courses.domain.errors import CourseError
from app.courses.domain.generation import GenerationMode
from app.courses.domain.style import LessonStyle
from app.courses.ports.spend import UsageTracking
from app.courses.ports.style import StylePlanner, StyleUnavailable, VoiceCatalog


def resolve_style(
    context: str,
    preferences: StyleInput | None,
    mode: GenerationMode,
    planner: StylePlanner | None,
    catalog: VoiceCatalog | None,
    previous: LessonStyle | None = None,
    tracking: UsageTracking | None = None,
    course_id: str | None = None,
    lesson_id: str | None = None,
) -> LessonStyle | None:
    if preferences is None and planner is None:
        return None
    preferences = preferences or StyleInput()
    # Validate explicit inputs even when the optional model integration is unavailable.
    requested_style(preferences)
    if (
        previous
        and previous.resolved
        and replace(preferences, review_output=previous.review_output) == style_input(previous)
    ):
        # Review-only changes do not require a voice catalog or another style-model call.
        return replace(
            previous, review_output=preferences.review_output, version=previous.version + 1
        )
    voices = catalog.list() if catalog else ()
    if preferences.voice_id and not any(v.id == preferences.voice_id for v in voices):
        raise CourseError("Choose an available narrator from the voice list")
    candidates = tuple(
        v
        for v in voices
        if any(
            label.partition(":")[0].strip().casefold() == "accent"
            and label.partition(":")[2].strip().casefold() == preferences.accent.casefold()
            for label in v.labels
        )
    )
    configured_fallback = (
        not candidates
        and len(voices) == 1
        and "catalog_permission_required" in voices[0].labels
        and not any(
            label.partition(":")[0].strip().casefold() == "accent" for label in voices[0].labels
        )
    )
    if configured_fallback:
        # A speech-only key still supports its configured narrator. Keep the requested
        # accent and disclose that it could not be verified rather than inventing labels.
        candidates = voices
    if voices and not candidates:
        raise StyleUnavailable(
            f"No verified {preferences.accent} narrator is available. "
            "Enable voices_read on the ElevenLabs key or choose another accent."
        )
    if preferences.voice_id and not any(v.id == preferences.voice_id for v in candidates):
        raise CourseError("Choose a narrator matching the selected accent")
    same_content = bool(
        previous
        and (preferences.description, preferences.audience, preferences.pacing)
        == (previous.request, previous.audience, previous.requested_pacing)
    )
    if (
        previous
        and previous.resolved
        and not (previous.requested_voice_id and not preferences.voice_id)
        and same_content
        and (preferences.accent, preferences.tone) == (previous.accent, previous.tone)
    ):
        resolved = previous
    elif planner:
        planning_voices = (
            tuple(v for v in candidates if v.id == preferences.voice_id)
            if preferences.voice_id
            else candidates
        )
        with tracking.scope(course_id, lesson_id, "style") if tracking else nullcontext():
            resolved = planner.resolve(
                context,
                preferences.description,
                preferences.audience,
                planning_voices,
                mode,
                accent=preferences.accent,
                tone=preferences.tone,
                pacing=preferences.pacing,
            )
        if previous and previous.resolved and same_content:
            # Voice controls must not rewrite an approved lesson or its visual direction.
            resolved = replace(
                previous,
                voice_id=resolved.voice_id,
                voice_description=resolved.voice_description,
                delivery=resolved.delivery,
            )
        resolved = replace(resolved, resolved=True)
    else:
        resolved = requested_style(preferences)
    selected = preferences.voice_id or resolved.voice_id
    voice = next((v for v in candidates if v.id == selected), candidates[0] if candidates else None)
    # Preserve explicit user text and audience; a planner cannot silently replace either.
    return replace(
        resolved,
        visual_style_id=preferences.visual_style_id,
        visual_style_version=1,
        review_output=preferences.review_output,
        request=preferences.description,
        audience=preferences.audience or resolved.audience,
        voice_notice=(
            f"Using the configured narrator because voice browsing is unavailable. "
            f"The requested {preferences.accent} accent cannot be verified. "
            "Enable voices_read on the ElevenLabs key to select a matching narrator."
            if configured_fallback
            else voice.description
            if voice and "catalog_permission_required" in voice.labels
            else ""
        ),
        requested_voice_id=preferences.voice_id,
        voice_id=voice.id if voice else "",
        voice_name=voice.name if voice else "Automatic",
        version=previous.version + 1 if previous else 1,
        resolved=resolved.resolved,
        accent=preferences.accent,
        tone=preferences.tone,
        requested_pacing=preferences.pacing,
        pacing=preferences.pacing or resolved.pacing,
    )


def requested_style(preferences: StyleInput | None) -> LessonStyle:
    preferences = preferences or StyleInput()
    return LessonStyle(
        request=preferences.description,
        audience=preferences.audience,
        voice_id=preferences.voice_id,
        requested_voice_id=preferences.voice_id,
        visual_style_id=preferences.visual_style_id,
        review_output=preferences.review_output,
        accent=preferences.accent,
        tone=preferences.tone,
        requested_pacing=preferences.pacing,
        resolved=False,
        summary="Style will be planned with your outline.",
    )


def draft_style(
    preferences: StyleInput | None, previous: LessonStyle | None, context_changed: bool
) -> LessonStyle | None:
    if preferences is None:
        if previous is None:
            return None
        preferences = style_input(previous)
    if (
        previous
        and preferences == style_input(previous)
        and not (context_changed and previous.resolved)
    ):
        return previous
    style = requested_style(preferences)
    return replace(style, version=previous.version + 1 if previous else 1)
