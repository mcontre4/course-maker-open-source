import math
import re
from dataclasses import dataclass

from app.courses.domain.errors import CourseError


class AnimationError(CourseError):
    pass


@dataclass(frozen=True)
class AnimationProject:
    lesson_id: str
    input_hash: str
    project_key: str
    output_hash: str
    model: str
    duration_sec: float
    status: str = "animation_ready"
    review_status: str = "legacy"
    backend: str = "codex"
    session_id: str | None = None
    reviewer_session_id: str | None = None
    owner_id: str | None = None
    job_id: str | None = None
    prepare_elements: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.prepare_elements) is not bool
            or self.backend not in {"codex", "direct"}
            or self.review_status
            not in {"legacy", "pending", "approved", "repaired", "skipped", "warning"}
            or not self.lesson_id
            or not re.fullmatch(r"[0-9a-f]{64}", self.input_hash)
            or not re.fullmatch(r"[0-9a-f]{64}", self.output_hash)
            or self.project_key
            not in {
                self.input_hash + "/remotion",
                self.input_hash + "/hyperframes",
                self.input_hash + "/javascript",
            }
            or not self.model
            or not math.isfinite(self.duration_sec)
            or not 0 < self.duration_sec <= 3600
            or self.status != "animation_ready"
        ):
            raise AnimationError("Invalid animation project")
