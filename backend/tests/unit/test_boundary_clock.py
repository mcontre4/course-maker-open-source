from pathlib import Path
from runpy import run_path

import pytest


@pytest.mark.parametrize(
    "source, rejected",
    [
        ("from datetime import datetime\nvalue = datetime.now()", True),
        ("from uuid import uuid4\nvalue = uuid4()", True),
        ("class Example:\n    def execute(self):\n        return self._clock.now()", True),
        (
            "from app.shared.domain.clock import Clock\nclass Example:\n"
            "    def __init__(self, clock: Clock):\n        self._clock = clock\n"
            "    def _timestamp(self):\n        return self._clock.now()",
            False,
        ),
    ],
)
def test_boundary_checker_allows_only_injected_clock_calls(tmp_path, source, rejected):
    checker = run_path(str(Path(__file__).parents[2] / "scripts/check_hexagonal_boundaries.py"))
    file = tmp_path / "app/courses/domain/example.py"
    file.parent.mkdir(parents=True)
    file.write_text(source)
    violations = checker["check_file"](tmp_path, file)
    assert bool(violations) is rejected
