from app.courses.application.base import _CourseUseCase
from app.courses.application.dto import (
    CourseResponse,
    LessonResponse,
    course_response,
    lesson_response,
)
from app.courses.application.requests import (
    CourseRequest,
    LessonLookupRequest,
    SubmitQuizRequest,
)
from app.courses.application.responses import (
    ProgressResponse,
    QuizAttemptResponse,
    QuizAttemptsResponse,
    QuizFeedbackResponse,
    QuizResultResponse,
)


class GetLesson(_CourseUseCase):
    def execute(self, request: LessonLookupRequest) -> LessonResponse:
        course = self._get(request.course_id)
        return lesson_response(course.lesson(request.lesson_id))


class ReviewLesson(_CourseUseCase):
    def execute(self, request: LessonLookupRequest) -> CourseResponse:
        with self._uow:
            course = self._get(request.course_id).review(request.lesson_id)
            self._courses.save(course)
            self._uow.commit()
        return course_response(course)


class SubmitQuiz(_CourseUseCase):
    def execute(self, request: SubmitQuizRequest) -> QuizResultResponse:
        with self._uow:
            course = self._get(request.course_id).submit(
                request.lesson_id, request.answers, f"attempt_{self._ids.new_uuid()}"
            )
            self._courses.save(course)
            self._uow.commit()
        attempt = course.attempts[-1]
        return QuizResultResponse(
            attempt.id,
            attempt.score,
            attempt.total,
            attempt.passed,
            tuple(
                QuizFeedbackResponse(a == q.answer, q.explanation)
                for a, q in zip(request.answers, course.lesson(request.lesson_id).quiz, strict=True)
            ),
            course_response(course),
        )


class GetProgress(_CourseUseCase):
    def execute(self, request: CourseRequest) -> ProgressResponse:
        course = self._get(request.course_id)
        total = sum(len(c.lessons) for c in course.chapters)
        return ProgressResponse(
            course.reviewed,
            course.completed,
            total,
            round(100 * len(course.completed) / total, 2) if total else 0,
        )


class GetQuizAttempts(_CourseUseCase):
    def execute(self, request: LessonLookupRequest) -> QuizAttemptsResponse:
        course = self._get(request.course_id)
        course.lesson(request.lesson_id)
        return QuizAttemptsResponse(
            tuple(
                QuizAttemptResponse(a.id, a.score, a.total, a.passed)
                for a in course.attempts
                if a.lesson_id == request.lesson_id
            )
        )
