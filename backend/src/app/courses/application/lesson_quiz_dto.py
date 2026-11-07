from dataclasses import dataclass
from typing import Literal

from app.courses.domain.generation import GenerationMode
from app.courses.domain.lesson_quiz import LessonQuiz, LessonQuizAttempt, LessonQuizQuestion


@dataclass(frozen=True)
class QuizQuestionInput:
    id: str
    kind: Literal["multiple_choice"]
    prompt: str
    options: tuple[str, ...]
    correct_index: int
    explanation: str


@dataclass(frozen=True)
class LessonQuizRequest:
    lesson_id: str
    owner_id: str


@dataclass(frozen=True)
class SaveLessonQuizRequest(LessonQuizRequest):
    questions: tuple[QuizQuestionInput, ...]
    expected_revision: int | None = None


@dataclass(frozen=True)
class GenerateLessonQuizRequest(LessonQuizRequest):
    generation_mode: GenerationMode = GenerationMode.BALANCED
    only_if_missing: bool = False
    session_id: str | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class PublicLessonQuizRequest:
    lesson_id: str


@dataclass(frozen=True)
class SubmitLessonQuizRequest:
    lesson_id: str
    learner_id: str
    answers: tuple[int, ...]
    quiz_revision: int


@dataclass(frozen=True)
class ListLessonQuizAttemptsRequest:
    lesson_id: str
    learner_id: str
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class QuizQuestionResponse:
    id: str
    kind: Literal["multiple_choice"]
    prompt: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class AuthorQuizQuestionResponse(QuizQuestionResponse):
    correct_index: int
    explanation: str


@dataclass(frozen=True)
class LessonQuizResponse:
    lesson_id: str
    questions: tuple[AuthorQuizQuestionResponse, ...]
    origin: Literal["generated", "edited"]
    revision: int
    session_id: str | None = None


@dataclass(frozen=True)
class PublicLessonQuizResponse:
    lesson_id: str
    questions: tuple[QuizQuestionResponse, ...]
    revision: int


@dataclass(frozen=True)
class QuizFeedbackResponse:
    question_id: str
    correct: bool
    explanation: str


@dataclass(frozen=True)
class LessonQuizAttemptResponse:
    id: str
    quiz_revision: int
    answers: tuple[int, ...]
    score: int
    total: int
    passed: bool
    submitted_at: str
    feedback: tuple[QuizFeedbackResponse, ...]


@dataclass(frozen=True)
class LessonQuizAttemptsResponse:
    items: tuple[LessonQuizAttemptResponse, ...]


def question_from_input(item: QuizQuestionInput) -> LessonQuizQuestion:
    return LessonQuizQuestion(
        item.id.strip(),
        item.kind,
        item.prompt.strip(),
        tuple(option.strip() for option in item.options),
        item.correct_index,
        item.explanation.strip(),
    )


def quiz_response(quiz: LessonQuiz) -> LessonQuizResponse:
    return LessonQuizResponse(
        str(quiz.lesson_id),
        tuple(
            AuthorQuizQuestionResponse(
                q.id, q.kind, q.prompt, q.options, q.correct_index, q.explanation
            )
            for q in quiz.questions
        ),
        quiz.origin,
        quiz.revision,
        quiz.session_id,
    )


def public_quiz_response(quiz: LessonQuiz) -> PublicLessonQuizResponse:
    return PublicLessonQuizResponse(
        str(quiz.lesson_id),
        tuple(QuizQuestionResponse(q.id, q.kind, q.prompt, q.options) for q in quiz.questions),
        quiz.revision,
    )


def attempt_response(attempt: LessonQuizAttempt) -> LessonQuizAttemptResponse:
    return LessonQuizAttemptResponse(
        str(attempt.id),
        attempt.quiz.revision,
        attempt.answers,
        attempt.score,
        len(attempt.quiz.questions),
        attempt.passed,
        attempt.submitted_at,
        tuple(
            QuizFeedbackResponse(q.id, answer == q.correct_index, q.explanation)
            for q, answer in zip(attempt.quiz.questions, attempt.answers, strict=True)
        ),
    )
