from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.courses.adapters.http.internal_access import require_internal_access
from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.spend import CourseSpendView
from app.courses.application.inspect_lesson import InspectLesson, InspectLessonRequest

router = APIRouter(
    prefix="/api/v1/internal",
    dependencies=[Depends(require_internal_access)],
    include_in_schema=False,
)


def get_inspector() -> InspectLesson:
    raise RuntimeError("Lesson inspector is not configured")


class LessonDiagnosticsView(HttpModel):
    lesson_id: str
    course_id: str | None
    title: str
    spend: CourseSpendView
    generation_seconds: float | None
    generation_active: bool


@router.get("/lessons/{lesson_id}", response_model=LessonDiagnosticsView)
@router.post("/lessons/{lesson_id}/refresh", response_model=LessonDiagnosticsView)
def inspect_lesson(
    lesson_id: str,
    request: Request,
    response: Response,
    service: Annotated[InspectLesson, Depends(get_inspector)],
    course_id: str | None = None,
) -> LessonDiagnosticsView:
    response.headers["Cache-Control"] = "no-store"
    return LessonDiagnosticsView.model_validate(
        service.execute(InspectLessonRequest(lesson_id, course_id, request.method == "POST"))
    )
