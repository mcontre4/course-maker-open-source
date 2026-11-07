from dataclasses import replace

from app.courses.application.base import _CourseUseCase
from app.courses.application.dto import (
    CourseResponse,
    course_response,
)
from app.courses.application.requests import (
    CourseRequest,
    EditTopicRequest,
    ReplaceSyllabusRequest,
)
from app.courses.application.syllabus_mapping import new_chapter


class ReplaceSyllabus(_CourseUseCase):
    def execute(self, request: ReplaceSyllabusRequest) -> CourseResponse:
        with self._uow:
            course = self._get(request.course_id)
            course.require_draft()
            chapters = tuple(new_chapter(chapter, self._ids) for chapter in request.chapters)
            updated = replace(course, chapters=chapters)
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)


class EditSyllabusTopic(_CourseUseCase):
    def execute(self, request: EditTopicRequest) -> CourseResponse:
        with self._uow:
            course = self._get(request.course_id).edit_topic(
                request.lesson_id, request.topic, request.operation
            )
            self._courses.save(course)
            self._uow.commit()
        return course_response(course)


class ApproveSyllabus(_CourseUseCase):
    def execute(self, request: CourseRequest) -> CourseResponse:
        with self._uow:
            course = self._get(request.course_id).approve()
            self._courses.save(course)
            self._uow.commit()
        return course_response(course)
