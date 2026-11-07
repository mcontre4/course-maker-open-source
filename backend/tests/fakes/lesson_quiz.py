from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Event

from app.courses.domain.lesson_quiz import LessonQuizQuestion
from app.courses.ports.lesson_quiz import QuizAgentResponse


def questions():
    return (
        LessonQuizQuestion(
            "question_1",
            "multiple_choice",
            "After score = 3, what is score?",
            ("3", "The word score", "An equality test"),
            0,
            "Assignment binds the name score to the value 3.",
        ),
    )


class InMemoryLessonQuizzes:
    def __init__(self):
        self.items = {}
        self.attempts = []

    def get_by_lesson_id(self, lesson_id):
        return self.items.get(str(lesson_id))

    def save(self, quiz):
        self.items[str(quiz.lesson_id)] = quiz

    def add_attempt(self, attempt):
        self.attempts.append(attempt)

    def list_attempts(self, lesson_id, learner_id, limit, offset):
        matches = [
            a
            for a in reversed(self.attempts)
            if a.quiz.lesson_id == lesson_id and a.learner_id == learner_id
        ]
        return tuple(matches[offset : offset + limit])


class RecordingQuizAgent:
    def __init__(self, uow=None):
        self.uow = uow
        self.calls = []
        self.during_run = None
        self.error = None

    def run(self, request):
        if self.uow:
            assert self.uow.exited, "LLM calls must be outside database transactions"
        self.calls.append(request)
        if self.during_run:
            self.during_run()
        if self.error:
            raise self.error
        return QuizAgentResponse(questions())


class FixedQuizClock:
    def now(self):
        return datetime(2026, 11, 1, 12, tzinfo=UTC)


class RecordingQuizTracking:
    def __init__(self):
        self.calls = []

    @contextmanager
    def scope(self, course_id, lesson_id, stage):
        self.calls.append((course_id, lesson_id, stage))
        yield


class RecordingQuizJobs:
    def __init__(self):
        self.jobs = []

    def enqueue(self, job):
        self.jobs.append(job)


class BlockingQuizAgent(RecordingQuizAgent):
    def __init__(self):
        super().__init__()
        self.started, self.release = Event(), Event()

    def run(self, request):
        self.started.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("Test did not release the quiz agent")
        return super().run(request)
