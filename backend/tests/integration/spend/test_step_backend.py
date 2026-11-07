from dataclasses import replace

import pytest

from app.courses.domain.spend import GenerationStep


@pytest.mark.integration
@pytest.mark.parametrize("backend", ["codex", "direct", None])
def test_step_backend_survives_reload_and_completion(spend_repository, backend):
    step = GenerationStep(
        "step_test", "course_test", "lesson_test", "animation", 100, backend=backend
    )
    spend_repository.save_step(step)
    assert spend_repository.list_steps(course_id="course_test") == (step,)
    finished = replace(step, finished_at=120)
    spend_repository.save_step(finished)
    assert spend_repository.list_steps(course_id="course_test") == (finished,)
