from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.generate_animation import GenerateAnimation, GenerateAnimationRequest
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator import StoryboardChangeRequired
from app.courses.ports.animator_model import AnimatorModel


class GenerateAnimationInput(HttpModel):
    message: str = Field(default="", max_length=2000)
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    reviewer_session_id: str | None = Field(default=None, min_length=1, max_length=100)
    job_id: str | None = Field(default=None, min_length=1, max_length=100)
    prepare_elements: bool = Field(default=False, strict=True)
    animator_model: AnimatorModel | None = None
    animation_backend: AnimationBackend = AnimationBackend.DIRECT
    generation_mode: GenerationMode = Field(default=GenerationMode.BALANCED, alias="generationMode")
    lesson_id: Annotated[str, Field(min_length=1, max_length=100)]
    visual_style: Annotated[str, Field(min_length=1, max_length=4000)]


def get_animation_generator() -> GenerateAnimation:
    raise RuntimeError("Animator is not configured")


def generate_animation(
    course_id: str,
    body: GenerateAnimationInput,
    owner: Owner,
    generator: Annotated[GenerateAnimation, Depends(get_animation_generator)],
) -> CourseView:
    return CourseView.model_validate(
        generator.execute(
            GenerateAnimationRequest(
                course_id,
                body.lesson_id,
                body.visual_style,
                body.generation_mode,
                body.animator_model,
                body.animation_backend,
                prepare_elements=body.prepare_elements,
                session_id=body.session_id,
                reviewer_session_id=body.reviewer_session_id,
                job_id=body.job_id,
                owner_id=owner,
                message=body.message,
            )
        )
    )


def change_required(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StoryboardChangeRequired)
    return JSONResponse(
        status_code=409,
        content={
            "detail": "storyboard_change_required",
            "change_request": asdict(exc.change),
        },
    )
