from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.courses.adapters.http.activity import RequestActivity, get_activity
from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.lesson_quiz import (
    GenerateLessonQuiz,
    GetLessonQuiz,
    GetPublicLessonQuiz,
    ListLessonQuizAttempts,
    SaveLessonQuiz,
    SubmitLessonQuiz,
)
from app.courses.application.lesson_quiz_dto import (
    GenerateLessonQuizRequest,
    LessonQuizRequest,
    ListLessonQuizAttemptsRequest,
    PublicLessonQuizRequest,
    QuizQuestionInput,
    SaveLessonQuizRequest,
    SubmitLessonQuizRequest,
)
from app.courses.domain.generation import GenerationMode

router = APIRouter(prefix="/api/v1/lessons", tags=["lesson quizzes"])
public_router = APIRouter(prefix="/api/v1/published/lessons", tags=["learner quizzes"])


class QuestionView(HttpModel):
    id: str
    kind: Literal["multiple_choice"]
    prompt: str
    options: tuple[str, ...]


class AuthorQuestionView(QuestionView):
    correct_index: int
    explanation: str


class PublicQuizView(HttpModel):
    lesson_id: str
    questions: tuple[QuestionView, ...]
    revision: int


class QuizView(PublicQuizView):
    session_id: str | None = None
    questions: tuple[AuthorQuestionView, ...]
    origin: Literal["generated", "edited"]


class QuestionInput(HttpModel):
    id: Annotated[str, Field(min_length=1, max_length=100)]
    kind: Literal["multiple_choice"]
    prompt: Annotated[str, Field(min_length=1, max_length=500)]
    options: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=300)], ...],
        Field(min_length=2, max_length=6),
    ]
    correct_index: Annotated[int, Field(ge=0, strict=True)]
    explanation: Annotated[str, Field(max_length=800)] = ""


class QuizInput(HttpModel):
    questions: Annotated[tuple[QuestionInput, ...], Field(min_length=1, max_length=20)]
    expected_revision: Annotated[int, Field(ge=0, strict=True)] | None = None


class GenerateQuizInput(HttpModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    job_id: str | None = Field(default=None, min_length=1, max_length=100)
    generation_mode: GenerationMode = GenerationMode.BALANCED
    only_if_missing: bool = False


class SubmitQuizInput(HttpModel):
    answers: Annotated[
        tuple[Annotated[int, Field(ge=0, strict=True)], ...], Field(min_length=1, max_length=20)
    ]
    quiz_revision: Annotated[int, Field(ge=1, strict=True)]


class FeedbackView(HttpModel):
    question_id: str
    correct: bool
    explanation: str


class AttemptView(HttpModel):
    id: str
    quiz_revision: int
    answers: tuple[int, ...]
    score: int
    total: int
    passed: bool
    submitted_at: datetime
    feedback: tuple[FeedbackView, ...]


class AttemptsView(HttpModel):
    items: tuple[AttemptView, ...]


def get_quiz() -> GetLessonQuiz:
    raise RuntimeError("Lesson quizzes are not configured")


def save_quiz() -> SaveLessonQuiz:
    raise RuntimeError("Lesson quizzes are not configured")


def generate_quiz() -> GenerateLessonQuiz:
    raise RuntimeError("Quiz generation is not configured")


def get_public_quiz() -> GetPublicLessonQuiz:
    raise RuntimeError("Lesson quizzes are not configured")


def submit_quiz() -> SubmitLessonQuiz:
    raise RuntimeError("Lesson quizzes are not configured")


def list_attempts() -> ListLessonQuizAttempts:
    raise RuntimeError("Lesson quizzes are not configured")


def quiz_activity(
    lesson_id: str, activity: Annotated[RequestActivity, Depends(get_activity)]
) -> Iterator[None]:
    key = f"generation-activity:lessons:{lesson_id}:quiz"
    token = activity.start(key, "quiz/generate", lease_seconds=600)
    try:
        yield
    except Exception:
        activity.failed(key, token)
        raise
    finally:
        activity.finish(key, token)


@router.get("/{lesson_id}/quiz")
def read_quiz(
    lesson_id: str, owner: Owner, service: Annotated[GetLessonQuiz, Depends(get_quiz)]
) -> QuizView | None:
    result = service.execute(LessonQuizRequest(lesson_id, owner))
    return QuizView.model_validate(result) if result else None


@router.put("/{lesson_id}/quiz")
def replace_quiz(
    lesson_id: str,
    body: QuizInput,
    owner: Owner,
    service: Annotated[SaveLessonQuiz, Depends(save_quiz)],
) -> QuizView:
    request = SaveLessonQuizRequest(
        lesson_id,
        owner,
        tuple(QuizQuestionInput(**q.model_dump()) for q in body.questions),
        body.expected_revision,
    )
    return QuizView.model_validate(service.execute(request))


@router.post("/{lesson_id}/quiz/generate", dependencies=[Depends(quiz_activity)])
def draft_quiz(
    lesson_id: str,
    body: GenerateQuizInput,
    owner: Owner,
    service: Annotated[GenerateLessonQuiz, Depends(generate_quiz)],
) -> QuizView:
    return QuizView.model_validate(
        service.execute(
            GenerateLessonQuizRequest(
                lesson_id,
                owner,
                body.generation_mode,
                body.only_if_missing,
                body.session_id,
                body.job_id,
            )
        )
    )


@public_router.get("/{lesson_id}/quiz")
def read_public_quiz(
    lesson_id: str, service: Annotated[GetPublicLessonQuiz, Depends(get_public_quiz)]
) -> PublicQuizView | None:
    result = service.execute(PublicLessonQuizRequest(lesson_id))
    return PublicQuizView.model_validate(result) if result else None


@public_router.post("/{lesson_id}/quiz/submit", status_code=201)
def grade_quiz(
    lesson_id: str,
    body: SubmitQuizInput,
    owner: Owner,
    service: Annotated[SubmitLessonQuiz, Depends(submit_quiz)],
) -> AttemptView:
    return AttemptView.model_validate(
        service.execute(SubmitLessonQuizRequest(lesson_id, owner, body.answers, body.quiz_revision))
    )


@public_router.get("/{lesson_id}/quiz/attempts")
def read_attempts(
    lesson_id: str,
    owner: Owner,
    service: Annotated[ListLessonQuizAttempts, Depends(list_attempts)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AttemptsView:
    return AttemptsView.model_validate(
        service.execute(ListLessonQuizAttemptsRequest(lesson_id, owner, limit, offset))
    )
