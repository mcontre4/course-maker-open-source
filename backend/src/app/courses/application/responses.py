from dataclasses import dataclass

from app.courses.application.dto import (
    CourseResponse,
)


@dataclass(frozen=True)
class ListCoursesResponse:
    items: tuple[CourseResponse, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class QuizFeedbackResponse:
    correct: bool
    explanation: str


@dataclass(frozen=True)
class QuizResultResponse:
    id: str
    score: int
    total: int
    passed: bool
    feedback: tuple[QuizFeedbackResponse, ...]
    course: CourseResponse


@dataclass(frozen=True)
class ProgressResponse:
    reviewed: tuple[str, ...]
    completed: tuple[str, ...]
    total_lessons: int
    percent: float


@dataclass(frozen=True)
class DeleteCourseResponse:
    deleted: bool


@dataclass(frozen=True)
class QuizAttemptResponse:
    id: str
    score: int
    total: int
    passed: bool


@dataclass(frozen=True)
class QuizAttemptsResponse:
    items: tuple[QuizAttemptResponse, ...]
