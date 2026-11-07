from dataclasses import FrozenInstanceError, replace

import pytest

from app.courses.domain.errors import CourseError


def test_script_is_validated_and_immutable(frozen_script):
    plan, board, script = frozen_script
    script.validate_plan(plan, 10)
    board.validate_script(script)
    assert script.segments[0].narration_text == board.scenes[0].narration_text
    assert replace(script.segments[0], visual_intent="Compare name and value").visual_intent
    with pytest.raises(FrozenInstanceError):
        script.segments[0].narration_text = "Changed"


@pytest.mark.parametrize(
    "change",
    [
        {"scene_id": ""},
        {"learning_purpose": ""},
        {"narration_text": ""},
        {"teaching_beat_index": 0},
        {"teaching_beat_index": True},
        {"target_duration_sec": 0},
        {"target_duration_sec": 301},
        {"target_duration_sec": True},
        {"equations": (" ",)},
        {"visual_intent": "x" * 501},
    ],
)
def test_script_segment_rejects_invalid_content(frozen_script, change):
    _, _, script = frozen_script
    with pytest.raises(CourseError):
        replace(script.segments[0], **change)


@pytest.mark.parametrize(
    "invalid",
    [
        "identity",
        "objectives",
        "empty",
        "duplicate",
        "minutes",
        "duration",
        "beat",
        "equation",
        "too_short",
        "target",
    ],
)
def test_script_rejects_invalid_lesson_contract(frozen_script, invalid):
    plan, _, script = frozen_script
    with pytest.raises(CourseError):
        if invalid == "identity":
            script = replace(script, lesson_id="other")
        elif invalid == "objectives":
            script = replace(script, objectives=())
        elif invalid == "empty":
            script = replace(script, segments=())
        elif invalid == "duplicate":
            script = replace(script, segments=(script.segments[0],) * 2)
        elif invalid == "minutes":
            script = replace(script, target_video_minutes=0)
        elif invalid == "duration":
            script = replace(script, segments=(replace(script.segments[0], target_duration_sec=1),))
        elif invalid == "beat":
            script = replace(
                script, segments=tuple(replace(s, teaching_beat_index=2) for s in script.segments)
            )
        elif invalid == "equation":
            plan = replace(plan, equations=("F = ma",))
        elif invalid == "too_short":
            script = replace(
                script,
                segments=tuple(replace(s, narration_text="Too short.") for s in script.segments),
            )
        elif invalid == "target":
            script.validate_plan(plan, 8)
        script.validate_plan(plan, 10)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scene_id", "changed"),
        ("teaching_beat_index", 2),
        ("learning_purpose", "Changed purpose"),
        ("narration_text", "Look at the name score. Changed narration."),
        ("target_duration_sec", 299),
        ("equations", ("F = ma",)),
    ],
)
def test_storyboard_cannot_change_frozen_segment(frozen_script, field, value):
    _, board, script = frozen_script
    changed = replace(board, scenes=(replace(board.scenes[0], **{field: value}), board.scenes[1]))
    with pytest.raises(CourseError, match="frozen script"):
        changed.validate_script(script)
