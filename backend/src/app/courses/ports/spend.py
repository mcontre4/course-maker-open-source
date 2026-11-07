from contextlib import AbstractContextManager
from typing import Protocol

from app.courses.domain.spend import GenerationStep, ModelCharge


class SpendRepository(Protocol):
    def save_step(self, step: GenerationStep) -> None: ...

    def list_steps(
        self, *, course_id: str | None = None, lesson_id: str | None = None
    ) -> tuple[GenerationStep, ...]: ...

    def list_by_course_id(self, course_id: str) -> tuple[ModelCharge, ...]: ...

    def list_by_lesson_id(self, lesson_id: str) -> tuple[ModelCharge, ...]: ...

    def save(self, charge: ModelCharge) -> None: ...


class Billing(Protocol):
    def resolve(self, charge: ModelCharge) -> ModelCharge: ...


class UsageTracking(Protocol):
    def scope(
        self, course_id: str | None, lesson_id: str | None, stage: str
    ) -> AbstractContextManager[None]: ...
