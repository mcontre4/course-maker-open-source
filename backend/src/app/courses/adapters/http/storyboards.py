from typing import Annotated

from fastapi import Depends
from pydantic import Field

from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.generate_storyboard import (
    GenerateStoryboard,
    GenerateStoryboardRequest,
)
from app.courses.domain.generation import GenerationMode


class GenerateStoryboardInput(HttpModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    script_session_id: str | None = Field(default=None, min_length=1, max_length=100)
    job_id: str | None = Field(default=None, min_length=1, max_length=100)
    message: str = Field(default="", max_length=2000)
    generation_mode: GenerationMode = Field(default=GenerationMode.BALANCED, alias="generationMode")
    lesson_id: Annotated[str, Field(min_length=1, max_length=100)]
    visual_style: Annotated[str | None, Field(min_length=1, max_length=4000)] = None


def get_storyboard_generator() -> GenerateStoryboard:
    raise RuntimeError("Storyboard generator is not configured")


def generate_storyboard(
    course_id: str,
    body: GenerateStoryboardInput,
    owner: Owner,
    generator: Annotated[GenerateStoryboard, Depends(get_storyboard_generator)],
) -> CourseView:
    return CourseView.model_validate(
        generator.execute(
            GenerateStoryboardRequest(
                course_id,
                body.lesson_id,
                body.visual_style,
                body.generation_mode,
                session_id=body.session_id,
                script_session_id=body.script_session_id,
                job_id=body.job_id,
                message=body.message,
                owner_id=owner,
            )
        )
    )
