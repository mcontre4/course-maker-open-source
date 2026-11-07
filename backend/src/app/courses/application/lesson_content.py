from app.courses.application.base import _CourseUseCase
from app.courses.application.dto import (
    CourseResponse,
    course_response,
)
from app.courses.application.requests import (
    UpdateLessonContentRequest,
)
from app.courses.application.syllabus_mapping import new_question


class UpdateLessonContent(_CourseUseCase):
    def execute(self, request: UpdateLessonContentRequest) -> CourseResponse:
        with self._uow:
            course = self._get(request.course_id)
            quiz = tuple(new_question(question, self._ids) for question in request.quiz)
            updated = course.set_content(
                request.lesson_id, request.video_url, quiz, request.video_asset_id
            )
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)
