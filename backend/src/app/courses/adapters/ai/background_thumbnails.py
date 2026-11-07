"""Dispatch optional illustrations without holding up the lesson pipeline."""

import logging
from collections.abc import Callable
from concurrent.futures import Executor

from app.courses.ports.thumbnail_jobs import ThumbnailJob


class BackgroundThumbnailJobs:
    def __init__(self, executor: Executor, generate: Callable[[ThumbnailJob], None]) -> None:
        self._executor, self._generate = executor, generate

    def enqueue(self, job: ThumbnailJob) -> None:
        try:
            self._executor.submit(self._run, job)
        except RuntimeError:
            logging.getLogger(__name__).exception("Background thumbnail could not be queued")

    def _run(self, job: ThumbnailJob) -> None:
        try:
            self._generate(job)
        except Exception:
            logging.getLogger(__name__).exception("Background thumbnail generation failed")
