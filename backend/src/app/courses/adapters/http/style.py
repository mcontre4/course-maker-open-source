from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.courses.adapters.http.schema import CourseView, HttpModel, StyleInputView
from app.courses.adapters.http.standalone import Owner, StandaloneLessonView
from app.courses.application.style import ListVoices, UpdateCourseStyle, UpdateStandaloneStyle
from app.courses.application.style_dto import (
    ListVoicesRequest,
    UpdateStyleRequest,
)
from app.courses.domain.generation import GenerationMode


class VoiceView(HttpModel):
    id: str
    name: str
    description: str
    preview_url: str | None
    labels: tuple[str, ...]


class VoiceListView(HttpModel):
    items: tuple[VoiceView, ...]


class UpdateStyleInput(HttpModel):
    style: StyleInputView | None
    expected_version: Annotated[int, Field(ge=0, strict=True)]
    generation_mode: GenerationMode = GenerationMode.BALANCED


def get_voices() -> ListVoices:
    raise RuntimeError("Voice catalog is not configured")


def get_course_style() -> UpdateCourseStyle:
    raise RuntimeError("Course style is not configured")


def get_lesson_style() -> UpdateStandaloneStyle:
    raise RuntimeError("Lesson style is not configured")


router = APIRouter(prefix="/api/v1", tags=["style"])


@router.get("/voices", response_model=VoiceListView)
def voices(
    service: Annotated[ListVoices, Depends(get_voices)],
    search: str = Query("", max_length=200),
) -> VoiceListView:
    return VoiceListView.model_validate(service.execute(ListVoicesRequest(search)))


@router.post("/lessons/{lesson_id}/style", response_model=StandaloneLessonView)
def update_lesson_style(
    lesson_id: str,
    body: UpdateStyleInput,
    owner: Owner,
    service: Annotated[UpdateStandaloneStyle, Depends(get_lesson_style)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            UpdateStyleRequest(
                lesson_id,
                body.style.to_request() if body.style else None,
                body.expected_version,
                owner_id=owner,
                generation_mode=body.generation_mode,
            )
        )
    )


@router.post("/courses/{course_id}/style", response_model=CourseView)
def update_course_style(
    course_id: str,
    body: UpdateStyleInput,
    service: Annotated[UpdateCourseStyle, Depends(get_course_style)],
) -> CourseView:
    return CourseView.model_validate(
        service.execute(
            UpdateStyleRequest(
                course_id,
                body.style.to_request() if body.style else None,
                body.expected_version,
                generation_mode=body.generation_mode,
            )
        )
    )


@router.post("/courses/{course_id}/lessons/{lesson_id}/style", response_model=CourseView)
def update_course_lesson_style(
    course_id: str,
    lesson_id: str,
    body: UpdateStyleInput,
    service: Annotated[UpdateCourseStyle, Depends(get_course_style)],
) -> CourseView:
    return CourseView.model_validate(
        service.execute(
            UpdateStyleRequest(
                course_id,
                body.style.to_request() if body.style else None,
                body.expected_version,
                lesson_id=lesson_id,
                generation_mode=body.generation_mode,
            )
        )
    )
