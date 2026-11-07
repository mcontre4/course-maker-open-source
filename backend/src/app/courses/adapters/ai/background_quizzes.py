import logging
from collections.abc import Callable
from concurrent.futures import Executor

from app.courses.ports.lesson_quiz import QuizJob


class BackgroundQuizJobs:
    def __init__(self, executor: Executor, generate: Callable[[QuizJob], None]) -> None:
        self._executor, self._generate = executor, generate

    def enqueue(self, job: QuizJob) -> None:
        try:
            self._executor.submit(self._run, job)
        except RuntimeError:
            logging.getLogger(__name__).exception("Background quiz could not be queued")

    def _run(self, job: QuizJob) -> None:
        try:
            self._generate(job)
        except Exception:
            logging.getLogger(__name__).exception("Background quiz generation failed")
