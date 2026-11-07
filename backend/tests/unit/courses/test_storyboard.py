from dataclasses import replace

import pytest
from fixtures.lesson_plan import lesson_plan
from fixtures.storyboard import storyboard
from fixtures.syllabus import make_planned_course

from app.courses.domain.errors import CourseError
from app.courses.domain.storyboard import SpeechCue


def test_cue_development_is_complete_when_supplied():
    with pytest.raises(CourseError):
        SpeechCue("c1", "the ray", "Trace the ray", focus="ray endpoint")
    cue = SpeechCue(
        "c1",
        "the ray",
        "Extend the ray",
        "ray endpoint",
        "Angle changes the intersection",
        "Hold the completed ray",
    )
    assert cue.relationship == "Angle changes the intersection"


@pytest.mark.parametrize(
    "invalid",
    [
        "empty",
        "duplicate_scene",
        "missing_anchor",
        "ambiguous_anchor",
        "duplicate_cue",
        "timing",
        "bool_duration",
        "accessibility",
        "beat",
        "order",
        "equation",
        "objective",
        "lesson",
        "short_script",
        "target",
    ],
)
def test_rejects_unusable_storyboard(invalid):
    _, curriculum = make_planned_course()
    plan = lesson_plan(curriculum.chapters[0].lessons[0])
    board = storyboard(plan)
    scene = board.scenes[0]
    with pytest.raises(CourseError):
        if invalid == "empty":
            board = replace(board, scenes=())
        elif invalid == "duplicate_scene":
            board = replace(board, scenes=(scene, scene))
        elif invalid == "missing_anchor":
            replace(scene, cues=(replace(scene.cues[0], anchor_text="absent"),))
        elif invalid == "ambiguous_anchor":
            replace(scene, cues=(replace(scene.cues[0], anchor_text="value"),))
        elif invalid == "duplicate_cue":
            replace(scene, cues=scene.cues * 2)
        elif invalid == "timing":
            board = replace(board, scenes=(replace(scene, target_duration_sec=1),))
        elif invalid == "bool_duration":
            replace(scene, target_duration_sec=True)
        elif invalid == "accessibility":
            replace(scene, accessibility_notes=())
        elif invalid == "beat":
            board = replace(
                board, scenes=tuple(replace(s, teaching_beat_index=2) for s in board.scenes)
            )
        elif invalid == "order":
            plan = replace(plan, beats=plan.beats * 2)
            board = replace(board, scenes=(replace(scene, teaching_beat_index=2), board.scenes[1]))
        elif invalid == "equation":
            plan = replace(plan, equations=("F = ma",))
        elif invalid == "objective":
            board = replace(board, objectives=("Other",))
        elif invalid == "lesson":
            board = replace(board, lesson_id="Other")
        elif invalid == "short_script":
            board = replace(
                board,
                scenes=tuple(
                    replace(s, narration_text="Look at the name score.") for s in board.scenes
                ),
            )
        elif invalid == "target":
            board.validate_plan(plan, 8)
        board.validate_plan(plan, 10)


def test_equations_accept_the_lesson_plan_text_limit():
    _, curriculum = make_planned_course()
    equation = "x = " + "a" * 5996
    plan = replace(lesson_plan(curriculum.chapters[0].lessons[0]), equations=(equation,))
    board = storyboard(plan)
    board.validate_plan(plan, 10)
    assert board.scenes[0].equations == (equation,)
    with pytest.raises(CourseError):
        replace(board.scenes[0], equations=(equation + "a",))


def test_overlapping_cue_occurrences_are_ambiguous():
    _, curriculum = make_planned_course()
    scene = storyboard(lesson_plan(curriculum.chapters[0].lessons[0])).scenes[0]
    with pytest.raises(CourseError, match="exactly once"):
        replace(
            scene,
            narration_text="a a a",
            cues=(replace(scene.cues[0], anchor_text="a a"),),
        )
