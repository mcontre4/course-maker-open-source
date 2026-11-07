from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ThumbnailJob:
    resource_id: str
    owner_id: str = ""
    course: bool = False
    lesson_id: str | None = None


class ThumbnailJobs(Protocol):
    def enqueue(self, job: ThumbnailJob) -> None: ...
