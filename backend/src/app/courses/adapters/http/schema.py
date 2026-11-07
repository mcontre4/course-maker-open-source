from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pydantic.alias_generators import to_camel

from app.courses.application.dto import (
    ChapterRequest,
    DurationRequest,
    LessonRequest,
    QuestionRequest,
)
from app.courses.application.lesson_plan_dto import LessonPlanResponse
from app.courses.application.style_dto import StyleInput, StyleResponse
from app.courses.domain.generation import GenerationMode


class HttpModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class TotalDuration(HttpModel):
    mode: Literal["total"]
    hours: Annotated[float, Field(ge=1, le=480, strict=True)]


class WeeklyDuration(HttpModel):
    mode: Literal["weekly"]
    weeks: Annotated[int, Field(ge=1, le=12, strict=True)]
    hours_per_week: Annotated[float, Field(ge=1, le=40, strict=True)]


class StyleInputView(HttpModel):
    visual_style_id: Literal[
        "flat-vector-science",
        "watercolor-wash",
        "tech-glow",
        "whiteboard",
        "halftone-pop",
        "risograph",
        "gouache-poster",
        "soft-3d",
        "memphis",
        "bauhaus",
        "swiss-grid",
    ]
    review_output: bool = Field(default=True, strict=True)
    description: Annotated[str, Field(max_length=2000)] = ""
    audience: Annotated[str, Field(max_length=2000)] = ""
    voice_id: Annotated[str, Field(max_length=100, pattern=r"^[A-Za-z0-9_-]*$")] = ""

    accent: Annotated[str, Field(max_length=60, pattern=r"^[A-Za-z][A-Za-z -]*$")] = "American"
    tone: Annotated[str, Field(max_length=100, pattern=r"^[^\[\]\r\n]*$")] = ""
    pacing: Literal["", "Relaxed", "Natural", "Brisk"] = ""

    def to_request(self) -> StyleInput:
        return StyleInput(
            self.description,
            self.audience,
            self.voice_id,
            visual_style_id=self.visual_style_id,
            review_output=self.review_output,
            accent=self.accent,
            tone=self.tone,
            pacing=self.pacing,
        )


class CourseInput(HttpModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    duration: Annotated[TotalDuration | WeeklyDuration, Field(discriminator="mode")]
    image: HttpUrl | Literal[""] = ""
    style: StyleInputView
    generation_mode: GenerationMode = GenerationMode.BALANCED

    def duration_request(self) -> DurationRequest:
        if isinstance(self.duration, TotalDuration):
            return DurationRequest("total", hours=self.duration.hours)
        return DurationRequest(
            "weekly", weeks=self.duration.weeks, hours_per_week=self.duration.hours_per_week
        )


class QuestionInput(HttpModel):
    prompt: Annotated[str, Field(min_length=1, max_length=2000)]
    options: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=1000)]],
        Field(min_length=2, max_length=10),
    ]
    answer: Annotated[int, Field(ge=0, strict=True)]
    explanation: Annotated[str, Field(min_length=1, max_length=4000)]


class LessonInput(HttpModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    topics: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=200)]],
        Field(min_length=1, max_length=50),
    ]
    minutes: Annotated[int, Field(ge=1, le=1440, strict=True)]
    image: HttpUrl | Literal[""] = ""
    style: StyleInputView | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    video_url: HttpUrl | None = None
    quiz: Annotated[list[QuestionInput], Field(max_length=50)] = []
    video_asset_id: str | None = None


class ChapterInput(HttpModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    summary: Annotated[str, Field(max_length=2000)] = ""
    image: HttpUrl | Literal[""] = ""
    style: StyleInputView | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    lessons: Annotated[list[LessonInput], Field(min_length=1, max_length=100)]


class SyllabusInput(HttpModel):
    chapters: Annotated[list[ChapterInput], Field(min_length=1, max_length=50)]

    def chapters_request(self) -> tuple[ChapterRequest, ...]:
        return tuple(
            ChapterRequest(
                c.title,
                c.summary,
                tuple(
                    LessonRequest(
                        lesson.title,
                        tuple(lesson.topics),
                        lesson.minutes,
                        str(lesson.image),
                        str(lesson.video_url) if lesson.video_url else None,
                        tuple(
                            QuestionRequest(q.prompt, tuple(q.options), q.answer, q.explanation)
                            for q in lesson.quiz
                        ),
                        video_asset_id=lesson.video_asset_id,
                    )
                    for lesson in c.lessons
                ),
                str(c.image),
            )
            for c in self.chapters
        )


class TopicInput(HttpModel):
    topic: Annotated[str, Field(min_length=1, max_length=200)]
    operation: Literal["add", "remove"]


class QuizInput(HttpModel):
    answers: Annotated[list[Annotated[int, Field(ge=0, strict=True)]], Field(max_length=50)]


class AssetInput(HttpModel):
    content_type: Literal["image/png", "image/jpeg", "image/webp", "video/mp4", "application/pdf"]
    size: Annotated[int, Field(ge=1, le=524288000, strict=True)]


class DurationView(HttpModel):
    mode: str
    hours: float | None
    weeks: int | None
    hours_per_week: float | None


class QuestionView(HttpModel):
    id: str
    prompt: str
    options: tuple[str, ...]


class StoryboardHttpModel(HttpModel):
    model_config = ConfigDict(str_strip_whitespace=False)


class SpeechCueView(StoryboardHttpModel):
    id: str
    anchor_text: str
    action: str
    focus: str = ""
    relationship: str = ""
    hold: str = ""


class StoryboardSceneView(StoryboardHttpModel):
    scene_id: str
    teaching_beat_index: int
    learning_purpose: str
    narration_text: str
    visual_brief: str
    cues: tuple[SpeechCueView, ...]
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


class StoryboardView(StoryboardHttpModel):
    lesson_id: str
    objectives: tuple[str, ...]
    target_video_minutes: int
    scenes: tuple[StoryboardSceneView, ...]


class TimedTextView(StoryboardHttpModel):
    text: str
    start_sec: float
    end_sec: float


class CueTimingView(StoryboardHttpModel):
    id: str
    anchor_text: str
    start_sec: float
    end_sec: float


class SpeechSettingsView(StoryboardHttpModel):
    voice_id: str
    model_id: str
    sample_rate: int
    stability: float
    similarity: float
    clone_strength: float
    delivery: str = ""


class AlignedSceneView(StoryboardHttpModel):
    scene_id: str
    transcript: str
    audio_key: str
    duration_sec: float
    timeline_start_sec: float
    words: tuple[TimedTextView, ...]
    cues: tuple[CueTimingView, ...]


class AlignmentView(StoryboardHttpModel):
    lesson_id: str
    storyboard_hash: str
    alignment_key: str
    status: str
    settings: SpeechSettingsView
    silence_between_scenes_sec: float
    duration_sec: float
    scenes: tuple[AlignedSceneView, ...]


class AnimationView(HttpModel):
    lesson_id: str
    input_hash: str
    project_key: str
    output_hash: str
    model: str
    duration_sec: float
    status: str
    review_status: str = "legacy"
    backend: str = "codex"
    session_id: str | None = None
    reviewer_session_id: str | None = None
    owner_id: str | None = None
    job_id: str | None = None
    prepare_elements: bool = False


class InteractiveSpecView(HttpModel):
    kind: str
    title: str
    objective: str
    explanation: str
    controls: tuple[str, ...]
    behavior: str
    prompts: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    initial_length: float
    initial_gravity: float
    initial_angle: float


class InteractiveView(StoryboardHttpModel):
    plan_hash: str
    reason: str
    spec: InteractiveSpecView | None
    html: str | None


class LessonView(HttpModel):
    agent_sessions: dict[str, str | None] | None = None
    id: str
    title: str
    topics: tuple[str, ...]
    minutes: int
    image: str
    video_url: str | None
    quiz: tuple[QuestionView, ...]
    video_asset_id: str | None
    plan: LessonPlanResponse | None = None
    storyboard: StoryboardView | None = None
    alignment: AlignmentView | None = None
    animation: AnimationView | None = None
    interactive: InteractiveView | None = None
    style: StyleResponse | None = None
    style_history: tuple[StyleResponse, ...] = ()


class ChapterView(HttpModel):
    id: str
    title: str
    summary: str
    image: str
    lessons: tuple[LessonView, ...]


class CourseView(HttpModel):
    owner_id: str | None = None
    id: str
    title: str
    description: str
    duration: DurationView
    image: str
    status: str
    chapters: tuple[ChapterView, ...]
    reviewed: tuple[str, ...]
    completed: tuple[str, ...]
    style: StyleResponse | None = None
    style_history: tuple[StyleResponse, ...] = ()


class CourseListView(HttpModel):
    items: tuple[CourseView, ...]
    total: int
    limit: int
    offset: int


class FeedbackView(HttpModel):
    correct: bool
    explanation: str


class QuizResultView(HttpModel):
    id: str
    score: int
    total: int
    passed: bool
    feedback: tuple[FeedbackView, ...]
    course: CourseView


class ProgressView(HttpModel):
    reviewed: tuple[str, ...]
    completed: tuple[str, ...]
    style: StyleResponse | None = None
    style_history: tuple[StyleResponse, ...] = ()
    total_lessons: int
    percent: float


class AssetView(HttpModel):
    id: str
    url: str
    method: str
    expires_in: int
    content_type: str | None
    size: int | None
    required_headers: tuple[tuple[str, str], ...]


class LessonContentInput(HttpModel):
    video_url: HttpUrl | None = None
    video_asset_id: str | None = None
    quiz: Annotated[list[QuestionInput], Field(max_length=50)] = []


class QuizAttemptView(HttpModel):
    id: str
    score: int
    total: int
    passed: bool


class QuizAttemptsView(HttpModel):
    items: tuple[QuizAttemptView, ...]
