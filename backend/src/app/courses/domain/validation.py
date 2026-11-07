from app.courses.domain.errors import CourseError


def text(value: str, maximum: int) -> None:
    if not value.strip() or len(value) > maximum:
        raise CourseError(f"Expected non-empty text of at most {maximum} characters")
