from dataclasses import dataclass

from app.courses.domain.errors import CourseError


@dataclass(frozen=True)
class UploadSpecification:
    content_type: str
    size: int

    def __post_init__(self) -> None:
        allowed_types = ("image/png", "image/jpeg", "image/webp", "video/mp4", "application/pdf")
        if (
            self.content_type not in allowed_types
            or type(self.size) is not int
            or not 1 <= self.size <= 524288000
        ):
            raise CourseError("Use a supported image, MP4, or PDF up to 500 MiB")
