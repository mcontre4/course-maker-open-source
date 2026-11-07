from dataclasses import dataclass
from typing import Literal

from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.identifiers import LessonId
from app.courses.domain.validation import text
from app.shared.domain.prefixed_uuid import PrefixedUuid


class LessonQuizAttemptId(PrefixedUuid):
    prefix = "quizattempt_"


@dataclass(frozen=True)
class LessonQuizQuestion:
    id: str
    kind: Literal["multiple_choice"]
    prompt: str
    options: tuple[str, ...]
    correct_index: int
    explanation: str

    def __post_init__(self) -> None:
        text(self.id, 100)
        text(self.prompt, 500)
        if self.kind != "multiple_choice" or not 2 <= len(self.options) <= 6:
            raise CourseError("Use multiple choice questions with 2–6 options")
        for option in self.options:
            text(option, 300)
        if len({option.strip().casefold() for option in self.options}) != len(self.options):
            raise CourseError("Each answer must be different")
        if type(self.correct_index) is not int or not 0 <= self.correct_index < len(self.options):
            raise CourseError("Choose a valid correct answer")
        if len(self.explanation) > 800:
            raise CourseError("Keep explanations under 800 characters")


@dataclass(frozen=True)
class LessonQuiz:
    lesson_id: LessonId
    questions: tuple[LessonQuizQuestion, ...]
    origin: Literal["generated", "edited"]
    revision: int = 1
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= len(self.questions) <= 20:
            raise CourseError("A quiz needs 1–20 questions")
        if len({question.id for question in self.questions}) != len(self.questions):
            raise CourseError("Question IDs must be unique")
        if self.origin not in ("generated", "edited") or self.revision < 1:
            raise CourseError("Invalid quiz provenance or revision")

    def require_revision(self, revision: int) -> None:
        if self.revision != revision:
            raise CourseConflict("Quiz changed; reload before continuing")


@dataclass(frozen=True)
class LessonQuizAttempt:
    id: LessonQuizAttemptId
    learner_id: str
    quiz: LessonQuiz
    answers: tuple[int, ...]
    submitted_at: str

    def __post_init__(self) -> None:
        text(self.learner_id, 100)
        if len(self.answers) != len(self.quiz.questions) or any(
            type(answer) is not int or not 0 <= answer < len(question.options)
            for answer, question in zip(self.answers, self.quiz.questions, strict=False)
        ):
            raise CourseError("Answer every question with a valid option index")

    @property
    def score(self) -> int:
        return sum(
            answer == question.correct_index
            for answer, question in zip(self.answers, self.quiz.questions, strict=True)
        )

    @property
    def passed(self) -> bool:
        return self.score == len(self.quiz.questions)
