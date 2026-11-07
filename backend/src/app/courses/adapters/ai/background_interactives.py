import logging
from collections.abc import Callable
from concurrent.futures import Executor

from app.courses.ports.lesson_interactive import InteractiveJob


class BackgroundInteractiveJobs:
    def __init__(self, executor: Executor, build: Callable[[InteractiveJob], None]) -> None:
        self._executor, self._build = executor, build

    def enqueue(self, job: InteractiveJob) -> None:
        # Let enqueue failures reach the use case so the persisted build becomes retryable.
        self._executor.submit(self._run, job)

    def _run(self, job: InteractiveJob) -> None:
        try:
            self._build(job)
        except Exception:
            logging.getLogger(__name__).exception("Background interactive build failed")
