"""The script/directing handoff to speech alignment and animation."""

import re
from dataclasses import dataclass, replace

from app.courses.domain.errors import CourseError
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.script import LessonScript
from app.courses.domain.validation import text


@dataclass(frozen=True)
class SpeechCue:
    id: str
    anchor_text: str
    action: str
    focus: str = ""
    relationship: str = ""
    hold: str = ""

    def __post_init__(self) -> None:
        text(self.id, 100)
        text(self.anchor_text, 500)
        text(self.action, 2000)
        development = (self.focus, self.relationship, self.hold)
        if any(development):
            for value in development:
                text(value, 500)


@dataclass(frozen=True)
class StoryboardScene:
    scene_id: str
    teaching_beat_index: int
    learning_purpose: str
    narration_text: str
    visual_brief: str
    cues: tuple[SpeechCue, ...]
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

    def with_narration(self, narration: str) -> "StoryboardScene":
        narration = narration.strip()
        text(narration, 16000)
        words = tuple(re.finditer(r"\S+", narration))
        cues = []
        for cue in self.cues:
            first = narration.find(cue.anchor_text)
            if first != -1 and narration.find(cue.anchor_text, first + 1) == -1:
                cues.append(cue)
                continue
            position = round(
                self.narration_text.index(cue.anchor_text)
                / len(self.narration_text)
                * (len(words) - 1)
            )
            anchor = narration
            for width in range(min(4, len(words)), min(24, len(words)) + 1):
                start = min(position, len(words) - width)
                candidate = narration[words[start].start() : words[start + width - 1].end()]
                first = narration.find(candidate)
                if len(candidate) <= 500 and narration.find(candidate, first + 1) == -1:
                    anchor = candidate
                    break
            if len(anchor) > 500:
                # A repeated passage may have no unique phrase near the old cue.
                for start in sorted(range(len(words)), key=lambda index: abs(index - position)):
                    end = min(start + 4, len(words)) - 1
                    candidate = narration[words[start].start() : words[end].end()]
                    first = narration.find(candidate)
                    if len(candidate) <= 500 and narration.find(candidate, first + 1) == -1:
                        anchor = candidate
                        break
            if len(anchor) > 500:
                raise CourseError(
                    "Use more varied narration so visual cues can be timed to unique phrases"
                )
            cues.append(replace(cue, anchor_text=anchor))
        return replace(self, narration_text=narration, cues=tuple(cues))

    def __post_init__(self) -> None:
        text(self.scene_id, 100)
        text(self.learning_purpose, 2000)
        text(self.narration_text, 16000)
        text(self.visual_brief, 8000)
        text(self.transition, 2000)
        for value in (*self.on_screen_text, *self.accessibility_notes):
            text(value, 2000)
        for equation in self.equations:
            text(equation, 6000)
        if type(self.teaching_beat_index) is not int or self.teaching_beat_index < 1:
            raise CourseError("Scenes need a positive teaching beat index")
        if type(self.target_duration_sec) is not int or not 1 <= self.target_duration_sec <= 300:
            raise CourseError("Scene duration estimates must be 1–300 integer seconds")
        if not self.accessibility_notes or not 1 <= len(self.cues) <= 20:
            raise CourseError("Scenes need accessibility notes and 1–20 speech cues")
        if len({cue.id for cue in self.cues}) != len(self.cues):
            raise CourseError("Cue IDs must be unique within a scene")
        for cue in self.cues:
            first = self.narration_text.find(cue.anchor_text)
            if first == -1 or self.narration_text.find(cue.anchor_text, first + 1) != -1:
                raise CourseError("Each cue anchor must occur exactly once in its scene narration")


@dataclass(frozen=True)
class Storyboard:
    lesson_id: str
    objectives: tuple[str, ...]
    target_video_minutes: int
    scenes: tuple[StoryboardScene, ...]

    def __post_init__(self) -> None:
        text(self.lesson_id, 100)
        for objective in self.objectives:
            text(objective, 6000)
        if not self.objectives or not 1 <= len(self.scenes) <= 120:
            raise CourseError("Storyboards need objectives and 1–120 ordered scenes")
        if type(self.target_video_minutes) is not int or not 1 <= self.target_video_minutes <= 1440:
            raise CourseError("Storyboards need positive integer target minutes")
        if len({scene.scene_id for scene in self.scenes}) != len(self.scenes):
            raise CourseError("Scene IDs must be unique")
        if (
            abs(sum(s.target_duration_sec for s in self.scenes) - self.target_video_minutes * 60)
            > 30
        ):
            raise CourseError("Scene estimates must fit the lesson budget within 30 seconds")

    def validate_plan(self, plan: LessonPlan, minutes: int) -> None:
        plan.require_feasible()
        if self.lesson_id != plan.lesson_id or self.objectives != plan.objectives:
            raise CourseError("Preserve the lesson plan ID and objectives exactly")
        if self.target_video_minutes != minutes:
            raise CourseError("Preserve the lesson target duration")
        indices = tuple(scene.teaching_beat_index for scene in self.scenes)
        if indices != tuple(sorted(indices)) or set(indices) != set(range(1, len(plan.beats) + 1)):
            raise CourseError("Cover every teaching beat in the plan's original order")
        if not set(plan.equations) <= {eq for scene in self.scenes for eq in scene.equations}:
            raise CourseError("Preserve every required equation verbatim in the storyboard")
        # Planning plausibility only. Measured TTS timing remains authoritative.
        words = sum(len(scene.narration_text.split()) for scene in self.scenes)
        if not minutes * 90 <= words <= minutes * 200:
            raise CourseError(
                "Write a full spoken script at roughly 90–200 words per target minute"
            )

    def validate_script(self, script: LessonScript) -> None:
        if (
            self.lesson_id != script.lesson_id
            or self.objectives != script.objectives
            or self.target_video_minutes != script.target_video_minutes
            or tuple(
                (
                    s.scene_id,
                    s.teaching_beat_index,
                    s.learning_purpose,
                    s.narration_text,
                    s.target_duration_sec,
                    s.equations,
                )
                for s in self.scenes
            )
            != tuple(
                (
                    s.scene_id,
                    s.teaching_beat_index,
                    s.learning_purpose,
                    s.narration_text,
                    s.target_duration_sec,
                    s.equations,
                )
                for s in script.segments
            )
        ):
            raise CourseError("Storyboard visual direction must preserve the frozen script exactly")


@dataclass(frozen=True)
class StoryboardGeneration:
    usage: PlanGeneration
    input_hash: str
    output_hash: str
    prompt_version: str
    visual_style: str | None
    status: str = "storyboard_ready"
    script_session_id: str | None = None

    def __post_init__(self) -> None:
        if self.status != "storyboard_ready":
            raise CourseError("Only validated storyboards can be saved as ready")
        for value in (self.input_hash, self.output_hash):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise CourseError("Storyboard version hashes must be SHA-256 digests")
        text(self.prompt_version, 100)
        if self.visual_style is not None:
            text(self.visual_style, 4000)
