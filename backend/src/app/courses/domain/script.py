"""Frozen narration owned by scripting, before any detailed visual direction."""

from dataclasses import dataclass

from app.courses.domain.errors import CourseError
from app.courses.domain.lesson_plan import LessonPlan
from app.courses.domain.validation import text


@dataclass(frozen=True)
class ScriptSegment:
    scene_id: str
    teaching_beat_index: int
    learning_purpose: str
    narration_text: str
    target_duration_sec: int
    equations: tuple[str, ...]
    visual_intent: str = ""

    def __post_init__(self) -> None:
        text(self.scene_id, 100)
        text(self.learning_purpose, 2000)
        text(self.narration_text, 16000)
        if type(self.teaching_beat_index) is not int or self.teaching_beat_index < 1:
            raise CourseError("Script segments need a positive teaching beat index")
        if type(self.target_duration_sec) is not int or not 1 <= self.target_duration_sec <= 300:
            raise CourseError("Script duration estimates must be 1–300 integer seconds")
        for equation in self.equations:
            text(equation, 6000)
        if self.visual_intent:
            text(self.visual_intent, 500)


@dataclass(frozen=True)
class LessonScript:
    lesson_id: str
    objectives: tuple[str, ...]
    target_video_minutes: int
    segments: tuple[ScriptSegment, ...]

    def __post_init__(self) -> None:
        text(self.lesson_id, 100)
        for objective in self.objectives:
            text(objective, 6000)
        if not self.objectives or not 1 <= len(self.segments) <= 100:
            raise CourseError("Scripts need objectives and 1–100 ordered segments")
        if type(self.target_video_minutes) is not int or not 1 <= self.target_video_minutes <= 1440:
            raise CourseError("Scripts need positive integer target minutes")
        if len({s.scene_id for s in self.segments}) != len(self.segments):
            raise CourseError("Script segment IDs must be unique")
        if (
            abs(sum(s.target_duration_sec for s in self.segments) - self.target_video_minutes * 60)
            > 30
        ):
            raise CourseError("Script estimates must fit the lesson budget within 30 seconds")

    def validate_plan(self, plan: LessonPlan, minutes: int) -> None:
        plan.require_feasible()
        if self.lesson_id != plan.lesson_id or self.objectives != plan.objectives:
            raise CourseError("Preserve the lesson plan ID and objectives exactly")
        if self.target_video_minutes != minutes:
            raise CourseError("Preserve the lesson target duration")
        indices = tuple(s.teaching_beat_index for s in self.segments)
        if indices != tuple(sorted(indices)) or set(indices) != set(range(1, len(plan.beats) + 1)):
            raise CourseError("Cover every teaching beat in the plan's original order")
        if not set(plan.equations) <= {eq for s in self.segments for eq in s.equations}:
            raise CourseError("Preserve every required equation verbatim in the script")
        words = sum(len(s.narration_text.split()) for s in self.segments)
        if not minutes * 90 <= words <= minutes * 200:
            raise CourseError(
                "Write a full spoken script at roughly 90–200 words per target minute"
            )
