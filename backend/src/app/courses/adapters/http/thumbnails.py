from typing import Annotated

from fastapi import APIRouter, Depends

from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.adapters.http.standalone import Owner, StandaloneLessonView
from app.courses.application.thumbnails import (
    GenerateCourseThumbnail,
    GenerateStandaloneThumbnail,
    ThumbnailRequest,
)


class ThumbnailInput(HttpModel):
    regenerate: bool = False


def get_course_thumbnail() -> GenerateCourseThumbnail:
    raise RuntimeError("Thumbnails are not configured")


def get_lesson_thumbnail() -> GenerateStandaloneThumbnail:
    raise RuntimeError("Thumbnails are not configured")


router = APIRouter(prefix="/api/v1", tags=["thumbnails"])


@router.post("/lessons/{lesson_id}/thumbnail", response_model=StandaloneLessonView)
def lesson_thumbnail(
    lesson_id: str,
    body: ThumbnailInput,
    owner: Owner,
    service: Annotated[GenerateStandaloneThumbnail, Depends(get_lesson_thumbnail)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(ThumbnailRequest(lesson_id, owner, regenerate=body.regenerate))
    )


@router.post("/courses/{course_id}/thumbnail", response_model=CourseView)
def course_thumbnail(
    course_id: str,
    body: ThumbnailInput,
    service: Annotated[GenerateCourseThumbnail, Depends(get_course_thumbnail)],
) -> CourseView:
    return CourseView.model_validate(
        service.execute(ThumbnailRequest(course_id, regenerate=body.regenerate))
    )


@router.post("/courses/{course_id}/lessons/{lesson_id}/thumbnail", response_model=CourseView)
def course_lesson_thumbnail(
    course_id: str,
    lesson_id: str,
    body: ThumbnailInput,
    service: Annotated[GenerateCourseThumbnail, Depends(get_course_thumbnail)],
) -> CourseView:
    return CourseView.model_validate(
        service.execute(
            ThumbnailRequest(course_id, lesson_id=lesson_id, regenerate=body.regenerate)
        )
    )
