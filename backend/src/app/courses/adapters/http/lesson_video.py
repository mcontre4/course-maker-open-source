import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse

from app.courses.adapters.http.standalone import Owner
from app.courses.application.lesson_playback import (
    GetCourseLessonPlayback,
    GetCourseLessonPlaybackRequest,
    GetStandaloneLessonPlayback,
    GetStandaloneLessonPlaybackRequest,
    LessonPlaybackResponse,
)
from app.courses.application.lesson_video import (
    GetCourseLessonVideo,
    GetCourseLessonVideoRequest,
    GetStandaloneLessonVideo,
    GetStandaloneLessonVideoRequest,
)

router = APIRouter(prefix="/api/v1", tags=["lesson playback"])


def get_standalone_video_reader() -> GetStandaloneLessonVideo:
    raise RuntimeError("Lesson playback is not configured")


def get_course_video_reader() -> GetCourseLessonVideo:
    raise RuntimeError("Lesson playback is not configured")


def video_response(content: bytes, byte_range: str | None) -> Response:
    size = len(content)
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, no-store"}
    if byte_range is None:
        return Response(content, media_type="video/mp4", headers=headers)
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range) if len(byte_range) < 128 else None
    if match and any(match.groups()):
        first, last = match.groups()
        if first:
            start, end = int(first), min(int(last) if last else size - 1, size - 1)
        else:
            start, end = max(0, size - int(last)), size - 1
        if 0 <= start <= end < size:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            return Response(
                content[start : end + 1], status_code=206, media_type="video/mp4", headers=headers
            )
    headers["Content-Range"] = f"bytes */{size}"
    return Response(status_code=416, headers=headers)


@router.get("/lessons/{lesson_id}/video")
def standalone_video(
    lesson_id: str,
    owner: Owner,
    service: Annotated[GetStandaloneLessonVideo, Depends(get_standalone_video_reader)],
    byte_range: Annotated[str | None, Header(alias="Range")] = None,
    v: str | None = None,
) -> Response:
    result = service.execute(GetStandaloneLessonVideoRequest(lesson_id, owner, v))
    return video_response(result.content, byte_range)


@router.get("/courses/{course_id}/lessons/{lesson_id}/video")
def course_video(
    course_id: str,
    lesson_id: str,
    service: Annotated[GetCourseLessonVideo, Depends(get_course_video_reader)],
    byte_range: Annotated[str | None, Header(alias="Range")] = None,
    v: str | None = None,
) -> Response:
    result = service.execute(GetCourseLessonVideoRequest(course_id, lesson_id, v))
    return video_response(result.content, byte_range)


def get_standalone_playback() -> GetStandaloneLessonPlayback:
    raise RuntimeError("Lesson playback is not configured")


def get_course_playback() -> GetCourseLessonPlayback:
    raise RuntimeError("Lesson playback is not configured")


def playback_response(result: LessonPlaybackResponse) -> Response:
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if result.preview_html is not None:
        headers["Content-Security-Policy"] = (
            "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; font-src data:; media-src data:; img-src data:; "
            "connect-src 'none'; form-action 'none'; base-uri 'none'"
        )
        return Response(result.preview_html, media_type="text/html", headers=headers)
    return JSONResponse(
        {"sourceHash": result.source_hash, "videoReady": result.video_ready}, headers=headers
    )


@router.get("/lessons/{lesson_id}/playback")
def standalone_playback(
    lesson_id: str,
    owner: Owner,
    service: Annotated[GetStandaloneLessonPlayback, Depends(get_standalone_playback)],
    v: str | None = None,
) -> Response:
    return playback_response(
        service.execute(GetStandaloneLessonPlaybackRequest(lesson_id, owner, source_hash=v))
    )


@router.get("/lessons/{lesson_id}/preview")
def standalone_preview(
    lesson_id: str,
    owner: Owner,
    service: Annotated[GetStandaloneLessonPlayback, Depends(get_standalone_playback)],
    v: str,
) -> Response:
    return playback_response(
        service.execute(GetStandaloneLessonPlaybackRequest(lesson_id, owner, True, v))
    )


@router.get("/courses/{course_id}/lessons/{lesson_id}/playback")
def course_playback(
    course_id: str,
    lesson_id: str,
    service: Annotated[GetCourseLessonPlayback, Depends(get_course_playback)],
    v: str | None = None,
) -> Response:
    return playback_response(
        service.execute(GetCourseLessonPlaybackRequest(course_id, lesson_id, source_hash=v))
    )


@router.get("/courses/{course_id}/lessons/{lesson_id}/preview")
def course_preview(
    course_id: str,
    lesson_id: str,
    service: Annotated[GetCourseLessonPlayback, Depends(get_course_playback)],
    v: str,
) -> Response:
    return playback_response(
        service.execute(GetCourseLessonPlaybackRequest(course_id, lesson_id, True, v))
    )
