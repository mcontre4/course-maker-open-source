from typing import Annotated

from fastapi import Depends
from pydantic import Field

from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.generate_lesson import GenerateLesson, GenerateLessonRequest
from app.courses.domain.generation import GenerationMode


class GenerateLessonInput(HttpModel):
    message: str = Field(default="", max_length=2000)
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    job_id: str | None = Field(default=None, min_length=1, max_length=100)
    generation_mode: GenerationMode = Field(default=GenerationMode.BALANCED, alias="generationMode")
    lesson_id: Annotated[str | None, Field(min_length=1, max_length=100)] = None


def get_lesson_generator() -> GenerateLesson:
    raise RuntimeError("Lesson generator is not configured")


def generate_lesson(
    course_id: str,
    owner: Owner,
    generator: Annotated[GenerateLesson, Depends(get_lesson_generator)],
    body: GenerateLessonInput | None = None,
) -> CourseView:
    return CourseView.model_validate(
        generator.execute(
            GenerateLessonRequest(
                course_id,
                body.lesson_id if body is not None else None,
                body.generation_mode if body is not None else GenerationMode.BALANCED,
                session_id=body.session_id if body else None,
                owner_id=owner,
                job_id=body.job_id if body else None,
                message=body.message if body else "",
            )
        )
    )
