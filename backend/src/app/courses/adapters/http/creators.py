from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import Field

from app.courses.adapters.http.lesson_video import video_response
from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.creators import (
    CreatorRequest,
    DiscoveryRequest,
    GetCreatorPage,
    GetDiscovery,
    GetOwnCreator,
    GetPublishedAnimation,
    GetPublishedLesson,
    PublishedLessonRequest,
    SaveCreator,
    SaveCreatorRequest,
)

router = APIRouter(prefix="/api/v1", tags=["creators"])


def get_own_creator() -> GetOwnCreator:
    raise RuntimeError("Creators are not configured")


def get_save_creator() -> SaveCreator:
    raise RuntimeError("Creators are not configured")


def get_creator_page() -> GetCreatorPage:
    raise RuntimeError("Creators are not configured")


def get_published_lesson() -> GetPublishedLesson:
    raise RuntimeError("Creators are not configured")


class CreatorView(HttpModel):
    id: str
    name: str
    picture: str | None


class PublishedLessonView(HttpModel):
    id: str
    title: str
    minutes: int
    image: str
    video_url: str | None
    course_id: str | None


class PublishedCourseView(HttpModel):
    id: str
    title: str
    description: str
    image: str
    lessons: tuple[PublishedLessonView, ...]


class CreatorPageView(HttpModel):
    creator: CreatorView
    lessons: tuple[PublishedLessonView, ...]
    courses: tuple[PublishedCourseView, ...]


class WatchLessonView(HttpModel):
    creator: CreatorView | None
    lesson: PublishedLessonView


class CreatorInput(HttpModel):
    name: str = Field(min_length=1, max_length=80)
    picture: str | None = Field(default=None, max_length=1_400_000)


@router.get("/creators/me")
def own_creator(
    owner: Owner, service: Annotated[GetOwnCreator, Depends(get_own_creator)]
) -> CreatorView:
    return CreatorView.model_validate(service.execute(CreatorRequest(owner)))


@router.put("/creators/me")
def save_creator(
    body: CreatorInput, owner: Owner, service: Annotated[SaveCreator, Depends(get_save_creator)]
) -> CreatorView:
    return CreatorView.model_validate(
        service.execute(SaveCreatorRequest(owner, body.name, body.picture))
    )


@router.get("/creators/{creator_id}")
def creator_page(
    creator_id: str, service: Annotated[GetCreatorPage, Depends(get_creator_page)]
) -> CreatorPageView:
    return CreatorPageView.model_validate(service.execute(CreatorRequest(creator_id)))


@router.get("/published/lessons/{lesson_id}")
def published_lesson(
    lesson_id: str,
    service: Annotated[GetPublishedLesson, Depends(get_published_lesson)],
    course_id: str | None = None,
) -> WatchLessonView:
    result = WatchLessonView.model_validate(
        service.execute(PublishedLessonRequest(lesson_id, course_id))
    )
    if result.lesson.video_url is None:
        result.lesson.video_url = f"/api/v1/published/lessons/{lesson_id}/video" + (
            f"?course_id={course_id}" if course_id else ""
        )
    return result


def get_discovery() -> GetDiscovery:
    raise RuntimeError("Discovery is not configured")


def get_published_animation() -> GetPublishedAnimation:
    raise RuntimeError("Public videos are not configured")


class DiscoveryView(HttpModel):
    lessons: tuple[PublishedLessonView, ...]
    courses: tuple[PublishedCourseView, ...]


@router.get("/published/discovery")
def discovery(
    service: Annotated[GetDiscovery, Depends(get_discovery)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
    q: Annotated[str, Query(max_length=200)] = "",
) -> DiscoveryView:
    return DiscoveryView.model_validate(service.execute(DiscoveryRequest(limit, q.strip())))


@router.get("/published/lessons/{lesson_id}/video")
def published_animation(
    lesson_id: str,
    service: Annotated[GetPublishedAnimation, Depends(get_published_animation)],
    course_id: str | None = None,
    byte_range: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    result = service.execute(PublishedLessonRequest(lesson_id, course_id))
    return video_response(result.content, byte_range)
