from dataclasses import asdict, replace

from fixtures.lesson_plan import lesson_plan
from fixtures.storyboard import storyboard
from fixtures.syllabus import make_planned_course

from app.courses.application.generate_storyboard import artifact_hash


def test_legacy_cue_fields_preserve_saved_narration_hashes():
    _, curriculum = make_planned_course()
    board = storyboard(lesson_plan(curriculum.chapters[0].lessons[0]))
    legacy_board = replace(
        board,
        scenes=tuple(
            replace(
                scene,
                cues=tuple(replace(cue, focus="", relationship="", hold="") for cue in scene.cues),
            )
            for scene in board.scenes
        ),
    )
    old_json = asdict(legacy_board)
    for scene in old_json["scenes"]:
        for cue in scene["cues"]:
            for key in ("focus", "relationship", "hold"):
                cue.pop(key)
    assert artifact_hash(asdict(legacy_board)) == artifact_hash(old_json)
    assert artifact_hash(asdict(board)) != artifact_hash(asdict(legacy_board))
