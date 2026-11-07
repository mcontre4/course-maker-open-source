"""Public creator identity, independent of account and contact details."""

import re
from dataclasses import dataclass

from app.courses.domain.errors import CourseError
from app.courses.domain.standalone import LessonOwnerId


@dataclass(frozen=True)
class CreatorProfile:
    id: LessonOwnerId
    name: str = "Creator"
    picture: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or self.name != self.name.strip() or len(self.name) > 80:
            raise CourseError("Creator name must contain 1–80 characters")
        if self.picture is not None and (
            len(self.picture) > 1_400_000
            or re.fullmatch(
                r"data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}", self.picture
            )
            is None
        ):
            raise CourseError("Use a PNG, JPEG or WebP profile picture up to 1 MB")
