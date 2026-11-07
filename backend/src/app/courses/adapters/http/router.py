from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.courses.adapters.http.animation import generate_animation
from app.courses.adapters.http.lessons import generate_lesson
from app.courses.adapters.http.schema import (
    AssetInput,
    AssetView,
    CourseInput,
    CourseListView,
    CourseView,
    LessonContentInput,
    LessonView,
    ProgressView,
    QuizAttemptsView,
    QuizInput,
    QuizResultView,
    SyllabusInput,
    TopicInput,
)
from app.courses.adapters.http.speech import generate_speech, read_speech_artifact
from app.courses.adapters.http.spend import CourseSpendView, read_spend, refresh_spend
from app.courses.adapters.http.standalone import Owner
from app.courses.adapters.http.storyboards import generate_storyboard
from app.courses.adapters.http.syllabus import generate_syllabus, get_session
from app.courses.application import use_cases as uc
from app.courses.application.assets import DownloadAssetRequest, UploadAssetRequest
from app.courses.application.catalog import CatalogRequest
from app.courses.application.dto import QuestionRequest
from app.courses.application.services import AssetServices, CatalogServices, CourseServices


# Composition root replaces these dependencies; adapters construct no infrastructure.
def get_courses() -> CourseServices:
    raise RuntimeError("Course services are not configured")


def get_assets() -> AssetServices:
    raise RuntimeError("Asset services are not configured")


def get_catalog() -> CatalogServices:
    raise RuntimeError("Catalog services are not configured")


def get_list_owner() -> str | None:
    return None


Services = Annotated[CourseServices, Depends(get_courses)]
Assets = Annotated[AssetServices, Depends(get_assets)]
router = APIRouter(prefix="/api/v1", tags=["courses"])


@router.post("/courses", response_model=CourseView, status_code=201)
def create_course(body: CourseInput, services: Services, owner: Owner) -> CourseView:
    return CourseView.model_validate(
        services.create.execute(
            uc.CreateCourseRequest(
                body.title,
                body.description,
                body.duration_request(),
                str(body.image),
                body.style.to_request() if body.style else None,
                body.generation_mode,
                owner_id=owner,
            )
        )
    )


@router.get("/courses", response_model=CourseListView)
def list_courses(
    services: Services,
    owner: Annotated[str | None, Depends(get_list_owner)],
    search: str = Query("", max_length=200),
    status: Literal["draft", "ready"] | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CourseListView:
    return CourseListView.model_validate(
        services.list.execute(uc.ListCoursesRequest(search, status, limit, offset, owner))
    )


@router.get("/courses/{course_id}", response_model=CourseView)
def get_course(course_id: str, services: Services) -> CourseView:
    return CourseView.model_validate(services.get.execute(uc.CourseRequest(course_id)))


@router.put("/courses/{course_id}", response_model=CourseView)
def update_course(course_id: str, body: CourseInput, services: Services) -> CourseView:
    return CourseView.model_validate(
        services.update.execute(
            uc.UpdateCourseRequest(
                course_id,
                body.title,
                body.description,
                body.duration_request(),
                str(body.image),
                body.style.to_request() if body.style else None,
                body.generation_mode,
            )
        )
    )


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: str, services: Services) -> Response:
    services.delete.execute(uc.CourseRequest(course_id))
    return Response(status_code=204)


@router.put("/courses/{course_id}/syllabus", response_model=CourseView)
def replace_syllabus(course_id: str, body: SyllabusInput, services: Services) -> CourseView:
    return CourseView.model_validate(
        services.syllabus.execute(uc.ReplaceSyllabusRequest(course_id, body.chapters_request()))
    )


@router.patch("/courses/{course_id}/lessons/{lesson_id}/topics", response_model=CourseView)
def edit_topic(course_id: str, lesson_id: str, body: TopicInput, services: Services) -> CourseView:
    return CourseView.model_validate(
        services.topic.execute(
            uc.EditTopicRequest(course_id, lesson_id, body.topic, body.operation)
        )
    )


@router.post("/courses/{course_id}/syllabus/approve", response_model=CourseView)
def approve_syllabus(course_id: str, services: Services) -> CourseView:
    return CourseView.model_validate(services.approve.execute(uc.CourseRequest(course_id)))


@router.get("/courses/{course_id}/lessons/{lesson_id}", response_model=LessonView)
def get_lesson(course_id: str, lesson_id: str, services: Services) -> LessonView:
    return LessonView.model_validate(
        services.lesson.execute(uc.LessonLookupRequest(course_id, lesson_id))
    )


@router.post("/courses/{course_id}/lessons/{lesson_id}/review", response_model=CourseView)
def review_lesson(course_id: str, lesson_id: str, services: Services) -> CourseView:
    return CourseView.model_validate(
        services.review.execute(uc.LessonLookupRequest(course_id, lesson_id))
    )


@router.post(
    "/courses/{course_id}/lessons/{lesson_id}/quiz/attempts",
    response_model=QuizResultView,
    status_code=201,
)
def submit_quiz(
    course_id: str, lesson_id: str, body: QuizInput, services: Services
) -> QuizResultView:
    return QuizResultView.model_validate(
        services.submit.execute(uc.SubmitQuizRequest(course_id, lesson_id, tuple(body.answers)))
    )


@router.get("/courses/{course_id}/progress", response_model=ProgressView)
def get_progress(course_id: str, services: Services) -> ProgressView:
    return ProgressView.model_validate(services.progress.execute(uc.CourseRequest(course_id)))


@router.post("/courses/{course_id}/assets/uploads", response_model=AssetView, status_code=201)
def upload_asset(course_id: str, body: AssetInput, services: Assets) -> AssetView:
    return AssetView.model_validate(
        services.upload.execute(UploadAssetRequest(course_id, body.content_type, body.size))
    )


@router.get("/courses/{course_id}/assets/{asset_id}/download", response_model=AssetView)
def download_asset(course_id: str, asset_id: str, services: Assets) -> AssetView:
    return AssetView.model_validate(
        services.download.execute(DownloadAssetRequest(course_id, asset_id))
    )


@router.get("/catalog/topics", tags=["catalog"])
def get_topics(
    services: Annotated[CatalogServices, Depends(get_catalog)],
) -> dict[str, tuple[str, ...]]:
    return {"topics": services.get.execute(CatalogRequest()).topics}


@router.post("/courses/{course_id}/chat", tags=["deferred AI"])
def deferred_ai(course_id: str, services: Services) -> None:
    services.get.execute(uc.CourseRequest(course_id))
    raise HTTPException(
        501,
        detail={
            "code": "ai_not_implemented",
            "message": "AI generation and tutor chat are deferred",
        },
    )


@router.put("/courses/{course_id}/lessons/{lesson_id}/content", response_model=CourseView)
def update_lesson_content(
    course_id: str, lesson_id: str, body: LessonContentInput, services: Services
) -> CourseView:
    return CourseView.model_validate(
        services.content.execute(
            uc.UpdateLessonContentRequest(
                course_id,
                lesson_id,
                str(body.video_url) if body.video_url else None,
                tuple(
                    QuestionRequest(q.prompt, tuple(q.options), q.answer, q.explanation)
                    for q in body.quiz
                ),
                body.video_asset_id,
            )
        )
    )


@router.get(
    "/courses/{course_id}/lessons/{lesson_id}/quiz/attempts", response_model=QuizAttemptsView
)
def get_quiz_attempts(course_id: str, lesson_id: str, services: Services) -> QuizAttemptsView:
    return QuizAttemptsView.model_validate(
        services.attempts.execute(uc.LessonLookupRequest(course_id, lesson_id))
    )


router.add_api_route(
    "/courses/{course_id}/syllabus/generate", generate_syllabus, methods=["POST"], tags=["syllabus"]
)
router.add_api_route(
    "/courses/{course_id}/syllabus/session", get_session, methods=["GET"], tags=["syllabus"]
)


router.add_api_route(
    "/courses/{course_id}/lessons/generate", generate_lesson, methods=["POST"], tags=["lessons"]
)

router.add_api_route(
    "/courses/{course_id}/storyboards/generate",
    generate_storyboard,
    methods=["POST"],
    tags=["lessons"],
)


router.add_api_route(
    "/courses/{course_id}/speech/generate",
    generate_speech,
    methods=["POST"],
    response_model=CourseView,
)


router.add_api_route(
    "/courses/{course_id}/lessons/{lesson_id}/speech/{kind}",
    read_speech_artifact,
    methods=["GET"],
    response_class=Response,
)

router.add_api_route(
    "/courses/{course_id}/animations/generate",
    generate_animation,
    methods=["POST"],
    response_model=CourseView,
)

router.add_api_route(
    "/courses/{course_id}/spend", read_spend, methods=["GET"], response_model=CourseSpendView
)
router.add_api_route(
    "/courses/{course_id}/spend/refresh",
    refresh_spend,
    methods=["POST"],
    response_model=CourseSpendView,
)
