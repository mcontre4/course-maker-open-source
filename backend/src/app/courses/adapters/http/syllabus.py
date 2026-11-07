from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.curriculum_dto import CurriculumResponse
from app.courses.application.generate_syllabus import (
    GenerateSyllabus,
    GenerateSyllabusRequest,
    GetSyllabusSession,
    SyllabusSessionRequest,
)
from app.courses.domain.generation import GenerationMode
from app.courses.ports.syllabus_agent import ConversationTurn


class GenerateSyllabusInput(BaseModel):
    session_id: str | None = Field(default=None, alias="sessionId", min_length=1, max_length=100)
    job_id: str | None = Field(default=None, alias="jobId", min_length=1, max_length=100)
    generation_mode: GenerationMode = Field(default=GenerationMode.BALANCED, alias="generationMode")
    model_config = {"extra": "forbid", "populate_by_name": True}
    message: str = Field(min_length=1, max_length=20000)
    expected_revision: int | None = Field(default=None, alias="expectedRevision", ge=0, strict=True)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value  # Preserve the user's message verbatim.


def get_generator() -> GenerateSyllabus:
    raise RuntimeError("Syllabus generation is not configured")


def get_syllabus_session() -> GetSyllabusSession:
    raise RuntimeError("Syllabus session is not configured")


class SyllabusSessionView(HttpModel):
    model_config = ConfigDict(alias_generator=None, str_strip_whitespace=False)
    session_id: str = Field(alias="sessionId")
    revision: int
    turns: tuple[ConversationTurn, ...]
    curriculum: CurriculumResponse | None


class GenerateSyllabusView(HttpModel):
    course: CourseView
    message: str
    session: SyllabusSessionView


# Route registration is performed in router.py so authentication applies uniformly.
def generate_syllabus(
    course_id: str,
    body: GenerateSyllabusInput,
    owner: Owner,
    service: Annotated[GenerateSyllabus, Depends(get_generator)],
) -> GenerateSyllabusView:
    result = service.execute(
        GenerateSyllabusRequest(
            course_id,
            body.message,
            body.expected_revision,
            body.generation_mode,
            body.session_id,
            owner,
            body.job_id,
        )
    )
    return GenerateSyllabusView.model_validate(result)


def get_session(
    course_id: str,
    owner: Owner,
    service: Annotated[GetSyllabusSession, Depends(get_syllabus_session)],
) -> SyllabusSessionView:
    return SyllabusSessionView.model_validate(
        service.execute(SyllabusSessionRequest(course_id, owner))
    )
