from dataclasses import dataclass

from app.courses.domain.storyboard import Storyboard


@dataclass(frozen=True)
class SpeechCueResponse:
    id: str
    anchor_text: str
    action: str
    focus: str = ""
    relationship: str = ""
    hold: str = ""


@dataclass(frozen=True)
class StoryboardSceneResponse:
    scene_id: str
    teaching_beat_index: int
    learning_purpose: str
    narration_text: str
    visual_brief: str
    cues: tuple[SpeechCueResponse, ...]
    target_duration_sec: int
    transition: str
    on_screen_text: tuple[str, ...]
    equations: tuple[str, ...]
    accessibility_notes: tuple[str, ...]
    object_ids: tuple[str, ...] = ()
    opening_composition: str = ""
    closing_composition: str = ""
    camera: str = ""
    continuity_from_previous: str = ""


@dataclass(frozen=True)
class StoryboardResponse:
    lesson_id: str
    objectives: tuple[str, ...]
    target_video_minutes: int
    scenes: tuple[StoryboardSceneResponse, ...]


def storyboard_response(board: Storyboard | None) -> StoryboardResponse | None:
    if board is None:
        return None
    return StoryboardResponse(
        board.lesson_id,
        board.objectives,
        board.target_video_minutes,
        tuple(
            StoryboardSceneResponse(
                s.scene_id,
                s.teaching_beat_index,
                s.learning_purpose,
                s.narration_text,
                s.visual_brief,
                tuple(
                    SpeechCueResponse(
                        c.id, c.anchor_text, c.action, c.focus, c.relationship, c.hold
                    )
                    for c in s.cues
                ),
                s.target_duration_sec,
                s.transition,
                s.on_screen_text,
                s.equations,
                s.accessibility_notes,
                s.object_ids,
                s.opening_composition,
                s.closing_composition,
                s.camera,
                s.continuity_from_previous,
            )
            for s in board.scenes
        ),
    )
