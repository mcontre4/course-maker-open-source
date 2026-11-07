from dataclasses import dataclass

from app.courses.application.dto import (
    ChapterRequest,
    DurationRequest,
    QuestionRequest,
)
from app.courses.application.style_dto import StyleInput
from app.courses.domain.generation import GenerationMode


@dataclass(frozen=True)
class CourseRequest:
    course_id: str


@dataclass(frozen=True)
class CreateCourseRequest:
    title: str
    description: str
    duration: DurationRequest
    image: str = ""
    style: StyleInput | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    owner_id: str | None = None


@dataclass(frozen=True)
class UpdateCourseRequest:
    course_id: str
    title: str
    description: str
    duration: DurationRequest
    image: str = ""
    style: StyleInput | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED


@dataclass(frozen=True)
class ListCoursesRequest:
    search: str = ""
    status: str | None = None
    limit: int = 20
    offset: int = 0
    owner_id: str | None = None


@dataclass(frozen=True)
class ReplaceSyllabusRequest:
    course_id: str
    chapters: tuple[ChapterRequest, ...]


@dataclass(frozen=True)
class EditTopicRequest:
    course_id: str
    lesson_id: str
    topic: str
    operation: str


@dataclass(frozen=True)
class LessonLookupRequest:
    course_id: str
    lesson_id: str


@dataclass(frozen=True)
class SubmitQuizRequest:
    course_id: str
    lesson_id: str
    answers: tuple[int, ...]


@dataclass(frozen=True)
class UpdateLessonContentRequest:
    course_id: str
    lesson_id: str
    video_url: str | None
    quiz: tuple[QuestionRequest, ...]
    video_asset_id: str | None = None
