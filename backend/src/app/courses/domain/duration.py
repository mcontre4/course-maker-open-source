from dataclasses import dataclass
from math import isfinite
from typing import Literal

from app.courses.domain.errors import CourseError


def _hours_in_range(value: float | None, maximum: int) -> bool:
    return (
        value is not None
        and not isinstance(value, bool)
        and isfinite(value)
        and 1 <= value <= maximum
    )


@dataclass(frozen=True)
class Duration:
    mode: Literal["total", "weekly"]
    hours: float | None = None
    weeks: int | None = None
    hours_per_week: float | None = None

    def __post_init__(self) -> None:
        if self.mode == "total":
            self._validate_total()
        elif self.mode == "weekly":
            self._validate_weekly()
        else:
            raise CourseError("Unknown duration mode")

    def _validate_total(self) -> None:
        if (
            not _hours_in_range(self.hours, 480)
            or self.weeks is not None
            or self.hours_per_week is not None
        ):
            raise CourseError("Choose between 1 and 480 total hours")

    def _validate_weekly(self) -> None:
        if (
            self.hours is not None
            or type(self.weeks) is not int
            or not 1 <= self.weeks <= 12
            or not _hours_in_range(self.hours_per_week, 40)
        ):
            raise CourseError("Choose 1–12 weeks and 1–40 hours per week")
