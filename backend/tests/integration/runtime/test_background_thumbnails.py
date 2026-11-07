from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.courses.adapters.ai.background_thumbnails import BackgroundThumbnailJobs
from app.courses.ports.thumbnail_jobs import ThumbnailJob

pytestmark = pytest.mark.integration


def test_optional_thumbnail_does_not_fail_saved_draft_when_executor_is_shutting_down(caplog):
    calls = []
    executor = ThreadPoolExecutor(max_workers=1)
    executor.shutdown()
    BackgroundThumbnailJobs(executor, calls.append).enqueue(ThumbnailJob("lesson_test", "owner"))
    assert not calls
    assert "could not be queued" in caplog.text


def test_failed_background_thumbnail_does_not_block_next_job(caplog):
    completed = Event()

    def generate(job):
        if job.resource_id == "failed":
            raise RuntimeError("Provider unavailable")
        completed.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        jobs = BackgroundThumbnailJobs(executor, generate)
        jobs.enqueue(ThumbnailJob("failed"))
        jobs.enqueue(ThumbnailJob("next"))
        assert completed.wait(5)
    assert "Background thumbnail generation failed" in caplog.text
