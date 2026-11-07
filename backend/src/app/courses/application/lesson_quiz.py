from contextlib import nullcontext

from app.courses.application.lesson_quiz_dto import (
    GenerateLessonQuizRequest,
    LessonQuizAttemptResponse,
    LessonQuizAttemptsResponse,
    LessonQuizRequest,
    LessonQuizResponse,
    ListLessonQuizAttemptsRequest,
    PublicLessonQuizRequest,
    PublicLessonQuizResponse,
    SaveLessonQuizRequest,
    SubmitLessonQuizRequest,
    attempt_response,
    public_quiz_response,
    question_from_input,
    quiz_response,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_quiz import LessonQuiz, LessonQuizAttempt, LessonQuizAttemptId
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.lesson_quiz import LessonQuizzes, QuizAgent, QuizAgentRequest
from app.courses.ports.spend import UsageTracking
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock
from app.shared.domain.id_generator import IdGenerator


class _QuizUseCase:
    def __init__(self, lessons: StandaloneLessons, quizzes: LessonQuizzes, uow: UnitOfWork) -> None:
        self._lessons, self._quizzes, self._uow = lessons, quizzes, uow

    def _published(self, lesson_id: str) -> LessonId:
        identifier = LessonId(lesson_id)
        lesson = self._lessons.require_by_id(identifier)
        if not lesson.content.is_published:
            raise CourseNotFound("Lesson not found")
        return identifier

    def _require_quiz(self, lesson_id: LessonId) -> LessonQuiz:
        quiz = self._quizzes.get_by_lesson_id(lesson_id)
        if quiz is None:
            raise CourseNotFound("Quiz not found")
        return quiz


class GetLessonQuiz(_QuizUseCase):
    def execute(self, request: LessonQuizRequest) -> LessonQuizResponse | None:
        with self._uow:
            lesson = self._lessons.require_by_id(LessonId(request.lesson_id))
            lesson.require_owner(request.owner_id)
            quiz = self._quizzes.get_by_lesson_id(lesson.content.id)
        return quiz_response(quiz) if quiz else None


class SaveLessonQuiz(_QuizUseCase):
    def execute(self, request: SaveLessonQuizRequest) -> LessonQuizResponse:
        questions = tuple(question_from_input(q) for q in request.questions)
        with self._uow:
            lesson = self._lessons.require_for_change(LessonId(request.lesson_id))
            lesson.require_owner(request.owner_id)
            previous = self._quizzes.get_by_lesson_id(lesson.content.id)
            revision = previous.revision if previous else 0
            if request.expected_revision is not None and request.expected_revision != revision:
                raise CourseConflict("Quiz changed; reload before continuing")
            quiz = LessonQuiz(lesson.content.id, questions, "edited", revision + 1)
            self._quizzes.save(quiz)
            self._uow.commit()
        return quiz_response(quiz)


class GenerateLessonQuiz(_QuizUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        quizzes: LessonQuizzes,
        uow: UnitOfWork,
        agent: QuizAgent,
        tracking: UsageTracking | None = None,
    ) -> None:
        super().__init__(lessons, quizzes, uow)
        self._agent, self._tracking = agent, tracking

    def execute(self, request: GenerateLessonQuizRequest) -> LessonQuizResponse:
        with self._uow:
            before = self._lessons.require_by_id(LessonId(request.lesson_id))
            before.require_owner(request.owner_id)
            previous = self._quizzes.get_by_lesson_id(before.content.id)
            if request.only_if_missing and previous:
                return quiz_response(previous)
            plan = before.content.plan
            if plan is None:
                raise CourseConflict("Generate a lesson outline before its quiz")
            plan.require_feasible()
        with (
            self._tracking.scope(None, request.lesson_id, "quiz")
            if self._tracking
            else nullcontext()
        ):
            generated = self._agent.run(
                QuizAgentRequest(
                    plan,
                    before.content.storyboard,
                    request.generation_mode,
                    session=AgentSessionContext(
                        request.owner_id, request.lesson_id, request.job_id, request.session_id
                    ),
                )
            )
        with self._uow:
            current = self._lessons.require_for_change(before.content.id)
            current.require_owner(request.owner_id)
            latest = self._quizzes.get_by_lesson_id(before.content.id)
            if (
                latest != previous
                or current.content.plan != plan
                or (
                    before.content.storyboard is not None
                    and current.content.storyboard != before.content.storyboard
                )
            ):
                raise CourseConflict("Lesson or quiz changed during generation; reload and retry")
            quiz = LessonQuiz(
                before.content.id,
                generated.questions,
                "generated",
                previous.revision + 1 if previous else 1,
                generated.session_id,
            )
            self._quizzes.save(quiz)
            self._uow.commit()
        return quiz_response(quiz)


class GetPublicLessonQuiz(_QuizUseCase):
    def execute(self, request: PublicLessonQuizRequest) -> PublicLessonQuizResponse | None:
        with self._uow:
            identifier = self._published(request.lesson_id)
            quiz = self._quizzes.get_by_lesson_id(identifier)
        return public_quiz_response(quiz) if quiz else None


class SubmitLessonQuiz(_QuizUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        quizzes: LessonQuizzes,
        uow: UnitOfWork,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        super().__init__(lessons, quizzes, uow)
        self._ids, self._clock = ids, clock

    def execute(self, request: SubmitLessonQuizRequest) -> LessonQuizAttemptResponse:
        with self._uow:
            identifier = self._published(request.lesson_id)
            quiz = self._require_quiz(identifier)
            quiz.require_revision(request.quiz_revision)
            attempt = LessonQuizAttempt(
                LessonQuizAttemptId.new(self._ids),
                request.learner_id,
                quiz,
                request.answers,
                self._clock.now().isoformat(),
            )
            self._quizzes.add_attempt(attempt)
            self._uow.commit()
        return attempt_response(attempt)


class ListLessonQuizAttempts(_QuizUseCase):
    def execute(self, request: ListLessonQuizAttemptsRequest) -> LessonQuizAttemptsResponse:
        if not 1 <= request.limit <= 100 or request.offset < 0:
            raise CourseError("Invalid quiz attempt pagination")
        with self._uow:
            identifier = self._published(request.lesson_id)
            attempts = self._quizzes.list_attempts(
                identifier, request.learner_id, request.limit, request.offset
            )
        return LessonQuizAttemptsResponse(tuple(attempt_response(a) for a in attempts))
