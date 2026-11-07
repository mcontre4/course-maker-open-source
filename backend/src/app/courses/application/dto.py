from dataclasses import asdict, dataclass
from typing import Literal

from app.courses.application.interactive_dto import InteractiveResponse, interactive_response
from app.courses.application.lesson_plan_dto import (
    LessonPlanResponse,
    ResearchSourceResponse,
    TeachingBeatResponse,
    WorkedExampleResponse,
)
from app.courses.application.speech_dto import AlignmentResponse, alignment_response
from app.courses.application.storyboard_dto import StoryboardResponse, storyboard_response
from app.courses.application.style_dto import StyleResponse, style_response
from app.courses.domain.course import Course
from app.courses.domain.duration import Duration
from app.courses.domain.syllabus import Chapter, Lesson


@dataclass(frozen=True)
class DurationRequest:
    mode: Literal["total", "weekly"]
    hours: float | None = None
    weeks: int | None = None
    hours_per_week: float | None = None


@dataclass(frozen=True)
class DurationResponse:
    mode: str
    hours: float | None
    weeks: int | None
    hours_per_week: float | None


@dataclass(frozen=True)
class QuestionRequest:
    prompt: str
    options: tuple[str, ...]
    answer: int
    explanation: str


@dataclass(frozen=True)
class LessonRequest:
    title: str
    topics: tuple[str, ...]
    minutes: int
    image: str = ""
    video_url: str | None = None
    quiz: tuple[QuestionRequest, ...] = ()
    video_asset_id: str | None = None


@dataclass(frozen=True)
class ChapterRequest:
    title: str
    summary: str
    lessons: tuple[LessonRequest, ...]
    image: str = ""


@dataclass(frozen=True)
class QuestionResponse:
    id: str
    prompt: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class AnimationResponse:
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


@dataclass(frozen=True)
class LessonResponse:
    id: str
    title: str
    topics: tuple[str, ...]
    minutes: int
    image: str
    video_url: str | None
    quiz: tuple[QuestionResponse, ...]
    video_asset_id: str | None
    plan: LessonPlanResponse | None = None
    storyboard: StoryboardResponse | None = None
    alignment: AlignmentResponse | None = None
    animation: AnimationResponse | None = None
    style: StyleResponse | None = None
    style_history: tuple[StyleResponse, ...] = ()
    interactive: InteractiveResponse | None = None
    agent_sessions: dict[str, str | None] | None = None


@dataclass(frozen=True)
class ChapterResponse:
    id: str
    title: str
    summary: str
    image: str
    lessons: tuple[LessonResponse, ...]


@dataclass(frozen=True)
class CourseResponse:
    id: str
    title: str
    description: str
    duration: DurationResponse
    image: str
    status: str
    chapters: tuple[ChapterResponse, ...]
    reviewed: tuple[str, ...]
    completed: tuple[str, ...]
    owner_id: str | None = None
    style: StyleResponse | None = None
    style_history: tuple[StyleResponse, ...] = ()


def duration_from_request(request: DurationRequest) -> Duration:
    return Duration(request.mode, request.hours, request.weeks, request.hours_per_week)


def lesson_response(lesson: Lesson) -> LessonResponse:
    return LessonResponse(
        str(lesson.id),
        lesson.title,
        lesson.topics,
        lesson.minutes,
        lesson.image,
        lesson.video_url,
        tuple(QuestionResponse(q.id, q.prompt, q.options) for q in lesson.quiz),
        lesson.video_asset_id,
        LessonPlanResponse(
            lesson.plan.lesson_id,
            lesson.plan.objectives,
            lesson.plan.assumed_knowledge,
            lesson.plan.introduced_knowledge,
            tuple(
                TeachingBeatResponse(
                    b.title,
                    b.purpose,
                    b.teaching_notes,
                    b.concepts,
                    b.seconds,
                    b.check_question,
                    b.expected_answer,
                )
                for b in lesson.plan.beats
            ),
            lesson.plan.required_facts,
            lesson.plan.equations,
            tuple(
                WorkedExampleResponse(e.problem, e.steps, e.result) for e in lesson.plan.examples
            ),
            lesson.plan.misconceptions,
            lesson.plan.scope_boundaries,
            tuple(ResearchSourceResponse(s.title, s.url) for s in lesson.plan.sources),
            lesson.plan.feasibility_status,
            lesson.plan.feasibility_explanation,
            lesson.plan.recommended_video_minutes,
            lesson.plan.recommended_scope_adjustment,
        )
        if lesson.plan
        else None,
        storyboard_response(lesson.storyboard),
        alignment_response(lesson.alignment),
        AnimationResponse(**asdict(lesson.animation)) if lesson.animation else None,
        style_response(lesson.style),
        tuple(
            item for v in lesson.previous_versions if (item := style_response(v.style)) is not None
        ),
        interactive_response(lesson.interactive),
        {
            "outline": lesson.plan_generation.session_id if lesson.plan_generation else None,
            "script": lesson.storyboard_generation.script_session_id
            if lesson.storyboard_generation
            else None,
            "storyboard": lesson.storyboard_generation.usage.session_id
            if lesson.storyboard_generation
            else None,
            "animator": lesson.animation.session_id if lesson.animation else None,
            "reviewer": lesson.animation.reviewer_session_id if lesson.animation else None,
        },
    )


def chapter_response(chapter: Chapter) -> ChapterResponse:
    return ChapterResponse(
        str(chapter.id),
        chapter.title,
        chapter.summary,
        chapter.image,
        tuple(lesson_response(lesson) for lesson in chapter.lessons),
    )


def course_response(course: Course) -> CourseResponse:
    duration = course.duration
    return CourseResponse(
        str(course.id),
        course.title,
        course.description,
        DurationResponse(duration.mode, duration.hours, duration.weeks, duration.hours_per_week),
        course.image,
        course.status,
        tuple(chapter_response(chapter) for chapter in course.chapters),
        course.reviewed,
        course.completed,
        course.owner_id,
        style_response(course.style),
        tuple(v for item in course.previous_styles if (v := style_response(item)) is not None),
    )
