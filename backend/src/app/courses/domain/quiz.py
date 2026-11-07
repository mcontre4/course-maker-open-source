from dataclasses import dataclass

from app.courses.domain.errors import CourseError
from app.courses.domain.validation import text


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    options: tuple[str, ...]
    answer: int
    explanation: str

    def __post_init__(self) -> None:
        text(self.id, 100)
        text(self.prompt, 2000)
        if not 2 <= len(self.options) <= 10:
            raise CourseError("A question needs 2–10 options")
        for option in self.options:
            text(option, 1000)
        if type(self.answer) is not int or not 0 <= self.answer < len(self.options):
            raise CourseError("Invalid correct answer")
        text(self.explanation, 4000)


@dataclass(frozen=True)
class QuizAttempt:
    id: str
    lesson_id: str
    answers: tuple[int, ...]
    score: int
    total: int
    passed: bool

    def __post_init__(self) -> None:
        if (
            not self.id
            or not self.lesson_id
            or not 1 <= self.total <= 50
            or len(self.answers) != self.total
            or not 0 <= self.score <= self.total
            or self.passed != (self.score == self.total)
        ):
            raise CourseError("Invalid quiz attempt")

    @classmethod
    def grade(
        cls,
        attempt_id: str,
        lesson_id: str,
        answers: tuple[int, ...],
        questions: tuple[Question, ...],
    ) -> "QuizAttempt":
        if (
            not questions
            or len(answers) != len(questions)
            or any(
                type(answer) is not int or not 0 <= answer < len(question.options)
                for answer, question in zip(answers, questions, strict=False)
            )
        ):
            raise CourseError("Answer every question with a valid option index")
        score = sum(
            answer == question.answer for answer, question in zip(answers, questions, strict=True)
        )
        return cls(attempt_id, lesson_id, answers, score, len(questions), score == len(questions))
