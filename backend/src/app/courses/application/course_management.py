from dataclasses import replace

from app.courses.application.base import _CourseUseCase
from app.courses.application.dto import (
    CourseResponse,
    course_response,
    duration_from_request,
)
from app.courses.application.requests import (
    CourseRequest,
    CreateCourseRequest,
    ListCoursesRequest,
    UpdateCourseRequest,
)
from app.courses.application.responses import (
    DeleteCourseResponse,
    ListCoursesResponse,
)
from app.courses.application.style_resolution import draft_style, requested_style
from app.courses.application.thumbnails import initial_thumbnail
from app.courses.domain.course import Course
from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.identifiers import CourseId
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.spend import UsageTracking
from app.courses.ports.thumbnail_jobs import ThumbnailJob, ThumbnailJobs
from app.courses.ports.thumbnails import ThumbnailGenerator
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


class CreateCourse(_CourseUseCase):
    def __init__(
        self,
        courses: CourseRepository,
        uow: UnitOfWork,
        ids: IdGenerator,
        thumbnails: ThumbnailGenerator | None = None,
        tracking: UsageTracking | None = None,
        thumbnail_jobs: ThumbnailJobs | None = None,
    ) -> None:
        super().__init__(courses, uow, ids)
        self._thumbnails, self._tracking = thumbnails, tracking
        self._thumbnail_jobs = thumbnail_jobs

    def execute(self, request: CreateCourseRequest) -> CourseResponse:
        course = Course(
            CourseId(f"course_{self._ids.new_uuid()}"),
            request.title.strip(),
            request.description.strip(),
            duration_from_request(request.duration),
            request.image,
            owner_id=request.owner_id,
        )
        course = replace(
            course, style=requested_style(request.style) if request.style is not None else None
        )
        with self._uow:
            self._courses.add(course)
            self._uow.commit()
        if self._thumbnail_jobs and not course.image:
            self._thumbnail_jobs.enqueue(ThumbnailJob(str(course.id), course=True))
        if not course.image:
            image = initial_thumbnail(
                self._thumbnails,
                self._tracking,
                course.title,
                course.description,
                style=course.style,
                course_id=str(course.id),
            )
            if image:
                with self._uow:
                    current = self._courses.require_for_syllabus_change(course.id)
                    if current != course:
                        return course_response(current)
                    course = replace(course, image=image)
                    self._courses.save(course)
                    self._uow.commit()
        return course_response(course)


class ListCourses(_CourseUseCase):
    def execute(self, request: ListCoursesRequest) -> ListCoursesResponse:
        if not 1 <= request.limit <= 100 or request.offset < 0:
            raise CourseError("Invalid pagination")
        if request.owner_id is None:
            courses = self._courses.list_courses(
                request.search, request.status, request.limit, request.offset
            )
            total = self._courses.count_courses(request.search, request.status)
        else:
            courses = self._courses.list_by_owner(
                request.owner_id, request.search, request.status, request.limit, request.offset
            )
            total = self._courses.count_by_owner(request.owner_id, request.search, request.status)
        return ListCoursesResponse(
            tuple(course_response(c) for c in courses),
            total,
            request.limit,
            request.offset,
        )


class GetCourse(_CourseUseCase):
    def execute(self, request: CourseRequest) -> CourseResponse:
        return course_response(self._get(request.course_id))


class UpdateCourse(_CourseUseCase):
    def execute(self, request: UpdateCourseRequest) -> CourseResponse:
        with self._uow:
            course = self._get(request.course_id)
            course.require_draft()
            duration = duration_from_request(request.duration)
            style = draft_style(
                request.style,
                course.style,
                (request.title.strip(), request.description.strip(), duration)
                != (course.title, course.description, course.duration),
            )
            if course.chapters and style != course.style:
                raise CourseConflict("Use the style editor after generating the syllabus")
            styled = course.restyle(style) if style != course.style else course
            updated = replace(
                styled,
                title=request.title.strip(),
                description=request.description.strip(),
                duration=duration,
                image=request.image or course.image,
            )
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)


class DeleteCourse(_CourseUseCase):
    def execute(self, request: CourseRequest) -> DeleteCourseResponse:
        with self._uow:
            self._courses.delete(self._get(request.course_id))
            self._uow.commit()
        return DeleteCourseResponse(True)
