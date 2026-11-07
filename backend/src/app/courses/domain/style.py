"""Provider-independent art direction shared by every lesson generation stage."""

import re
from dataclasses import dataclass, replace

from app.courses.domain.curriculum import CourseGuide
from app.courses.domain.errors import CourseError
from app.courses.domain.visual_style import VisualStyle


@dataclass(frozen=True)
class LessonStyle:
    request: str = ""
    audience: str = ""
    summary: str = "Clear, approachable teaching with readable diagrams and natural narration."
    teaching: str = "Use concrete examples and introduce concepts before applying them."
    writing: str = "Clear, conversational explanations; preserve educational accuracy."
    visuals: str = "Readable educational diagrams with consistent typography and clear contrast."
    motion: str = "Purposeful, restrained reveals that support understanding."
    pacing: str = "Natural pacing with time to understand each idea."
    voice_description: str = "A clear, friendly educational narrator."
    delivery: str = ""
    voice_id: str = ""
    requested_voice_id: str = ""
    voice_name: str = "Automatic"
    version: int = 1
    voice_notice: str = ""
    resolved: bool = True
    visual_style_id: str = "flat-vector-science"
    visual_style_version: int = 1
    review_output: bool = True
    accent: str = "American"
    tone: str = ""
    requested_pacing: str = ""

    def __post_init__(self) -> None:
        VisualStyle(self.visual_style_id, self.visual_style_version)
        if type(self.review_output) is not bool:
            raise CourseError("Choose whether to review the final video")
        if not re.fullmatch(r"[A-Za-z][A-Za-z -]{0,59}", self.accent):
            raise CourseError("Choose a valid accent")
        if len(self.tone) > 100 or any(c in self.tone for c in "[]\n\r"):
            raise CourseError("Tone must be at most 100 characters without brackets or line breaks")
        if self.requested_pacing not in ("", "Relaxed", "Natural", "Brisk"):
            raise CourseError("Choose an available pacing option")
        if not 1 <= self.version <= 1000:
            raise CourseError("Style version must be between 1 and 1000")
        for value in (self.request, self.audience):
            if len(value) > 2000:
                raise CourseError("Style and audience must be at most 2000 characters")
        for value in (
            self.summary,
            self.teaching,
            self.writing,
            self.visuals,
            self.motion,
            self.pacing,
            self.voice_description,
            self.voice_name,
        ):
            if not value.strip() or len(value) > 1000:
                raise CourseError("Style directions must contain 1–1000 characters")
        if len(self.delivery) > 200 or any(c in self.delivery for c in "[]\n\r"):
            raise CourseError("Voice delivery must be a short instruction without brackets")
        for voice_id in (self.voice_id, self.requested_voice_id):
            if voice_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", voice_id):
                raise CourseError("Invalid voice ID")

    def speech_delivery(self) -> str:
        # Explicit controls take precedence over inferred delivery. Keep provider tags bounded.
        accent = f"{self.accent} accent"
        tone = self.tone or self.delivery
        pacing = f"{self.requested_pacing.lower()} pacing" if self.requested_pacing else ""
        suffix = "; ".join(part for part in (accent, pacing) if part)
        return "; ".join(part for part in (tone[: 198 - len(suffix)], suffix) if part)

    def visual_direction(self) -> str:
        return (
            f"{VisualStyle(self.visual_style_id, self.visual_style_version).direction()}\n"
            f"Visuals: {self.visuals}\nMotion: {self.motion}\nPacing: {self.pacing}"
        )

    def directions(self) -> str:
        return (
            f"{self.summary}\nCreator's explicit style request: {self.request or 'None'}\n"
            "Presentation guidance below does not add required subject coverage.\n"
            f"Audience: {self.audience or 'Use the learner description'}\n"
            f"Teaching: {self.teaching}\nWriting: {self.writing}\n"
            f"{self.visual_direction()}\nNarration: {self.voice_description}\n"
            f"Accent: {self.accent}\nTone: {self.tone or 'Match topic and audience'}"
        )

    def apply_to_guide(self, guide: CourseGuide) -> CourseGuide:
        return replace(guide, style=self.directions())

    def change_scope(self, previous: "LessonStyle | None") -> str:
        if previous is None or any(
            getattr(self, key) != getattr(previous, key)
            for key in ("audience", "teaching", "writing", "pacing")
        ):
            return "content"
        if (self.visuals, self.motion, self.visual_style_id, self.visual_style_version) != (
            previous.visuals,
            previous.motion,
            previous.visual_style_id,
            previous.visual_style_version,
        ):
            return "visuals"
        if (self.voice_id, self.speech_delivery()) != (
            previous.voice_id,
            previous.speech_delivery(),
        ):
            return "voice"
        if self.review_output != previous.review_output:
            return "review"
        return "none"
