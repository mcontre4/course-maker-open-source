from dataclasses import asdict

from app.courses.domain.script import LessonScript, ScriptSegment


def script_from_board(board):
    return LessonScript(
        board.lesson_id,
        board.objectives,
        board.target_video_minutes,
        tuple(
            ScriptSegment(
                s.scene_id,
                s.teaching_beat_index,
                s.learning_purpose,
                s.narration_text,
                s.target_duration_sec,
                s.equations,
            )
            for s in board.scenes
        ),
    )


def visual_output(board):
    fields = {
        "scene_id",
        "visual_brief",
        "cues",
        "transition",
        "on_screen_text",
        "accessibility_notes",
        "object_ids",
        "opening_composition",
        "closing_composition",
        "camera",
        "continuity_from_previous",
    }
    return {"scenes": [{k: v for k, v in asdict(s).items() if k in fields} for s in board.scenes]}
