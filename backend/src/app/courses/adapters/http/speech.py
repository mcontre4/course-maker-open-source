from typing import Annotated

from fastapi import Depends, Response
from pydantic import Field

from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.application.generate_speech import GenerateSpeech, GenerateSpeechRequest
from app.courses.application.get_speech_artifact import GetSpeechArtifact, GetSpeechArtifactRequest


class GenerateSpeechInput(HttpModel):
    lesson_id: Annotated[str, Field(min_length=1, max_length=100)]


def get_speech_generator() -> GenerateSpeech:
    raise RuntimeError("Speech generator is not configured")


def get_speech_reader() -> GetSpeechArtifact:
    raise RuntimeError("Speech reader is not configured")


def read_speech_artifact(
    course_id: str,
    lesson_id: str,
    kind: str,
    reader: Annotated[GetSpeechArtifact, Depends(get_speech_reader)],
    scene_id: str | None = None,
) -> Response:
    result = reader.execute(GetSpeechArtifactRequest(course_id, lesson_id, kind, scene_id))
    return Response(
        result.content,
        media_type=result.content_type,
        headers={"Cache-Control": "private, no-store"},
    )


def generate_speech(
    course_id: str,
    body: GenerateSpeechInput,
    generator: Annotated[GenerateSpeech, Depends(get_speech_generator)],
) -> CourseView:
    return CourseView.model_validate(
        generator.execute(GenerateSpeechRequest(course_id, body.lesson_id))
    )
