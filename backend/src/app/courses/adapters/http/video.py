from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field

from app.courses.adapters.http.activity import RequestActivity, get_activity
from app.courses.adapters.http.router import get_courses
from app.courses.adapters.http.schema import CourseView, HttpModel
from app.courses.adapters.http.standalone import (
    AnimationRevisionInput,
    Owner,
    RevisionInput,
    StandaloneLessonView,
    get_lesson,
)
from app.courses.application.generate_automatic import GenerateAutomaticLesson
from app.courses.application.generate_video import (
    GenerateCourseVideo,
    GenerateCourseVideoRequest,
    GenerateStandaloneScript,
    GenerateStandaloneVideo,
)
from app.courses.application.requests import CourseRequest
from app.courses.application.services import CourseServices
from app.courses.application.standalone import GetStandaloneLesson
from app.courses.application.standalone_dto import (
    ReviseStandaloneLessonRequest,
    StandaloneLessonRequest,
)
from app.courses.domain.generation import GenerationMode
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator_model import AnimatorModel


def get_standalone_script() -> GenerateStandaloneScript:
    raise RuntimeError("Script generation is not configured")


def get_automatic_lesson() -> GenerateAutomaticLesson:
    raise RuntimeError("Automatic generation is not configured")


def get_standalone_video() -> GenerateStandaloneVideo:
    raise RuntimeError("Video generation is not configured")


def get_course_video() -> GenerateCourseVideo:
    raise RuntimeError("Video generation is not configured")


class AutomaticLessonInput(AnimationRevisionInput):
    message: Annotated[str, Field(max_length=2000)] = ""


class CourseVideoInput(HttpModel):
    prepare_elements: bool = Field(default=False, strict=True)
    animator_model: AnimatorModel | None = None
    animation_backend: AnimationBackend = AnimationBackend.DIRECT
    lesson_id: Annotated[str, Field(min_length=1, max_length=100)]
    generation_mode: GenerationMode = GenerationMode.BALANCED


router = APIRouter(prefix="/api/v1", tags=["video generation"])


@router.post("/lessons/{lesson_id}/generation/cancel")
def cancel_lesson_generation(
    lesson_id: str,
    owner: Owner,
    service: Annotated[GetStandaloneLesson, Depends(get_lesson)],
    activity: Annotated[RequestActivity, Depends(get_activity)],
) -> dict[str, bool]:
    service.execute(StandaloneLessonRequest(lesson_id, owner))
    return {"cancelled": activity.cancel(f"generation-activity:lessons:{lesson_id}")}


@router.post("/courses/{course_id}/generation/cancel")
def cancel_course_generation(
    course_id: str,
    services: Annotated[CourseServices, Depends(get_courses)],
    activity: Annotated[RequestActivity, Depends(get_activity)],
) -> dict[str, bool]:
    services.get.execute(CourseRequest(course_id))
    return {"cancelled": activity.cancel(f"generation-activity:courses:{course_id}")}


@router.post("/lessons/{lesson_id}/script/generate", response_model=StandaloneLessonView)
def standalone_script(
    lesson_id: str,
    body: RevisionInput,
    owner: Owner,
    service: Annotated[GenerateStandaloneScript, Depends(get_standalone_script)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                body.expected_revision,
                generation_mode=body.generation_mode,
                regenerate_from=body.regenerate_from,
            )
        )
    )


@router.post("/lessons/{lesson_id}/automatic", response_model=StandaloneLessonView)
def automatic_lesson(
    lesson_id: str,
    body: AutomaticLessonInput,
    owner: Owner,
    service: Annotated[GenerateAutomaticLesson, Depends(get_automatic_lesson)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                body.expected_revision,
                message=body.message,
                generation_mode=body.generation_mode,
                regenerate_from=body.regenerate_from,
                animator_model=body.animator_model,
                prepare_elements=body.prepare_elements,
                animation_backend=body.animation_backend,
            )
        )
    )


@router.post("/lessons/{lesson_id}/video", response_model=StandaloneLessonView)
def standalone_video(
    lesson_id: str,
    body: AnimationRevisionInput,
    owner: Owner,
    service: Annotated[GenerateStandaloneVideo, Depends(get_standalone_video)],
) -> StandaloneLessonView:
    return StandaloneLessonView.model_validate(
        service.execute(
            ReviseStandaloneLessonRequest(
                lesson_id,
                owner,
                body.expected_revision,
                generation_mode=body.generation_mode,
                regenerate_from=body.regenerate_from,
                animator_model=body.animator_model,
                prepare_elements=body.prepare_elements,
                animation_backend=body.animation_backend,
            )
        )
    )


@router.post("/courses/{course_id}/video/generate", response_model=CourseView)
def course_video(
    course_id: str,
    body: CourseVideoInput,
    service: Annotated[GenerateCourseVideo, Depends(get_course_video)],
) -> CourseView:
    return CourseView.model_validate(
        service.execute(
            GenerateCourseVideoRequest(
                course_id,
                body.lesson_id,
                body.generation_mode,
                body.animator_model,
                body.animation_backend,
                prepare_elements=body.prepare_elements,
            )
        )
    )
