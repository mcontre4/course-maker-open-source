from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.courses.adapters.http.animation import change_required
from app.courses.application.errors import StorageUnavailable
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.speech import AlignmentError
from app.courses.ports.animator import AnimationUnavailable, StoryboardChangeRequired
from app.courses.ports.lesson_agent import LessonGenerationUnavailable
from app.courses.ports.lesson_quiz import QuizGenerationUnavailable
from app.courses.ports.lesson_video import LessonVideoUnavailable
from app.courses.ports.speech import SpeechArtifactUnavailable, SpeechUnavailable
from app.courses.ports.storyboard_agent import StoryboardGenerationUnavailable
from app.courses.ports.style import StyleUnavailable
from app.courses.ports.syllabus_errors import SyllabusUnavailable
from app.courses.ports.thumbnails import ThumbnailUnavailable


async def course_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def not_found(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def conflict(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def storage_unavailable(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Cloud Storage is unavailable"})


async def syllabus_unavailable(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(QuizGenerationUnavailable, syllabus_unavailable)
    app.add_exception_handler(LessonVideoUnavailable, syllabus_unavailable)
    app.add_exception_handler(ThumbnailUnavailable, syllabus_unavailable)
    app.add_exception_handler(StyleUnavailable, syllabus_unavailable)
    app.add_exception_handler(AnimationUnavailable, syllabus_unavailable)
    app.add_exception_handler(StoryboardChangeRequired, change_required)
    app.add_exception_handler(SpeechUnavailable, syllabus_unavailable)
    app.add_exception_handler(SpeechArtifactUnavailable, syllabus_unavailable)
    app.add_exception_handler(AlignmentError, syllabus_unavailable)
    app.add_exception_handler(LessonGenerationUnavailable, syllabus_unavailable)
    app.add_exception_handler(StoryboardGenerationUnavailable, syllabus_unavailable)
    app.add_exception_handler(CourseError, course_error)
    app.add_exception_handler(CourseNotFound, not_found)
    app.add_exception_handler(CourseConflict, conflict)
    app.add_exception_handler(StorageUnavailable, storage_unavailable)
    app.add_exception_handler(SyllabusUnavailable, syllabus_unavailable)
