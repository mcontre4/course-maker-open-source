from dataclasses import dataclass, replace

from app.courses.application.standalone_dto import (
    StandaloneLessonResponse,
    standalone_response,
)
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.lesson_interactive import InteractiveId, InteractiveLesson
from app.courses.domain.lesson_quiz import LessonQuiz
from app.courses.domain.standalone import LessonFlow, LessonOwnerId, StandaloneLesson
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.lesson_interactive import LessonInteractives
from app.courses.ports.lesson_quiz import LessonQuizzes
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class CopyLessonRequest:
    lesson_id: str
    owner_id: str
    course_id: str | None = None
    title: str | None = None


class CopyLesson:
    def __init__(
        self,
        lessons: StandaloneLessons,
        courses: CourseRepository,
        uow: UnitOfWork,
        ids: IdGenerator,
        quizzes: LessonQuizzes | None = None,
        interactives: LessonInteractives | None = None,
    ) -> None:
        self._lessons, self._courses, self._uow, self._ids = lessons, courses, uow, ids
        self._quizzes = quizzes
        self._interactives = interactives

    def execute(self, request: CopyLessonRequest) -> StandaloneLessonResponse:
        owner = LessonOwnerId(request.owner_id)
        with self._uow:
            if request.course_id:
                course = self._courses.require_by_id(CourseId(request.course_id))
                content = course.lesson(str(LessonId(request.lesson_id)))
                content = replace(content, style=content.style or course.style)
                owns_source = course.owner_id == request.owner_id
                description = content.title
                approved = content.plan is not None
            else:
                source = self._lessons.require_by_id(LessonId(request.lesson_id))
                content = source.content
                owns_source = source.owner_id == owner
                description = source.description if owns_source else content.title
                approved = source.approved
            if not owns_source:
                published = content.playback_version()
                if published is None or not published.is_published:
                    raise CourseNotFound("Lesson not found")
                content = published
                description = published.title
                approved = published.plan is not None
            copied = StandaloneLesson(
                owner,
                description,
                content.copy(
                    LessonId.new(self._ids), include_history=owns_source, title=request.title
                ),
                approved=(
                    approved
                    and content.plan is not None
                    and content.plan.feasibility_status != "infeasible"
                ),
                flow=LessonFlow.GUIDED,
            )
            self._lessons.add(copied)
            if self._quizzes and not request.course_id:
                quiz = self._quizzes.get_by_lesson_id(LessonId(request.lesson_id))
                if quiz:
                    self._quizzes.save(LessonQuiz(copied.content.id, quiz.questions, quiz.origin))
            if self._interactives:
                target = InteractiveLesson(copied.content, str(owner), copied.description, "")
                for item in self._interactives.list_by_lesson_id(LessonId(request.lesson_id)):
                    activity = item.copy(
                        InteractiveId.new(self._ids), copied.content.id, include_drafts=owns_source
                    )
                    if activity:
                        self._interactives.add(activity, target)
            self._uow.commit()
        return standalone_response(copied)
