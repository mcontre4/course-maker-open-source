from dataclasses import asdict, dataclass

from app.courses.domain.generation import GenerationMode
from app.courses.domain.style import LessonStyle


@dataclass(frozen=True)
class StyleInput:
    description: str = ""
    audience: str = ""
    voice_id: str = ""
    visual_style_id: str = "flat-vector-science"
    review_output: bool = True
    accent: str = "American"
    tone: str = ""
    pacing: str = ""


def style_input(style: LessonStyle) -> StyleInput:
    return StyleInput(
        style.request,
        style.audience,
        style.requested_voice_id,
        visual_style_id=style.visual_style_id,
        review_output=style.review_output,
        accent=style.accent,
        tone=style.tone,
        pacing=style.requested_pacing,
    )


@dataclass(frozen=True)
class StyleResponse:
    request: str
    audience: str
    summary: str
    teaching: str
    writing: str
    visuals: str
    motion: str
    pacing: str
    voice_description: str
    delivery: str
    voice_id: str
    voice_name: str
    version: int
    requested_voice_id: str = ""
    voice_notice: str = ""
    resolved: bool = True
    visual_style_id: str = "flat-vector-science"
    visual_style_version: int = 1
    review_output: bool = True
    accent: str = "American"
    tone: str = ""
    requested_pacing: str = ""


def style_response(style: LessonStyle | None) -> StyleResponse | None:
    return StyleResponse(**asdict(style)) if style else None


@dataclass(frozen=True)
class UpdateStyleRequest:
    resource_id: str
    style: StyleInput | None
    expected_version: int
    owner_id: str = ""
    lesson_id: str | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED


@dataclass(frozen=True)
class ListVoicesRequest:
    search: str = ""


@dataclass(frozen=True)
class VoiceResponse:
    id: str
    name: str
    description: str
    preview_url: str | None
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ListVoicesResponse:
    items: tuple[VoiceResponse, ...]
    notice: str = ""
