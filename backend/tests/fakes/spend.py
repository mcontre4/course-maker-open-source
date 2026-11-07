from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal

from app.courses.domain.spend import ModelCharge


class InMemorySpend:
    def __init__(self):
        self.charges = {}
        self.steps = {}

    def save_step(self, step):
        self.steps[step.id] = step

    def list_steps(self, *, course_id=None, lesson_id=None):
        return tuple(
            s
            for s in self.steps.values()
            if (
                s.course_id == course_id
                if course_id is not None
                else s.course_id is None and s.lesson_id == lesson_id
            )
        )

    def save(self, charge: ModelCharge):
        self.charges[charge.id] = charge

    def list_by_course_id(self, course_id: str):
        return tuple(c for c in self.charges.values() if c.course_id == course_id)

    def list_by_lesson_id(self, lesson_id: str):
        return tuple(
            c for c in self.charges.values() if c.course_id is None and c.lesson_id == lesson_id
        )


class FixedBilling:
    def __init__(self, cost=Decimal("0.002")):
        self.cost = cost
        self.calls = []

    def resolve(self, charge):
        self.calls.append(charge)
        return replace(charge, usd=self.cost)


class RecordingUsageTracking:
    def __init__(self):
        self.calls = []
        self.active = False

    @contextmanager
    def scope(self, course_id: str, lesson_id: str | None, stage: str) -> Iterator[None]:
        self.calls.append((course_id, lesson_id, stage))
        self.active = True
        try:
            yield
        finally:
            self.active = False
