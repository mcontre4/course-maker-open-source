from contextlib import nullcontext
from dataclasses import replace

from app.courses.application.guide_memory import guide_with_memories, load_memory_guidance
from app.courses.application.standalone_dto import (
    CreateStandaloneLessonRequest,
    ListStandaloneLessonsRequest,
    ListStandaloneLessonsResponse,
    ReviseStandaloneLessonRequest,
    StandaloneLessonRequest,
    StandaloneLessonResponse,
    UpdateStandaloneLessonRequest,
    standalone_response,
)
from app.courses.application.style_resolution import draft_style, requested_style, resolve_style
from app.courses.application.thumbnail_merge import without_lesson_image
from app.courses.application.thumbnails import initial_thumbnail
from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson, lesson_details
from app.courses.domain.syllabus import Lesson
from app.courses.domain.validation import text
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.guide import GuideRepository
from app.courses.ports.lesson_agent import LessonAgent, LessonAgentRequest
from app.courses.ports.spend import UsageTracking
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.courses.ports.style import StylePlanner, VoiceCatalog
from app.courses.ports.thumbnail_jobs import ThumbnailJob, ThumbnailJobs
from app.courses.ports.thumbnails import ThumbnailGenerator
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


class _StandaloneUseCase:
    def __init__(self, lessons: StandaloneLessons, uow: UnitOfWork) -> None:
        self._lessons, self._uow = lessons, uow

    def _load(self, lesson_id: str, owner_id: str, *, lock: bool = False) -> StandaloneLesson:
        identifier = LessonId(lesson_id)
        lesson = (
            self._lessons.require_for_change(identifier)
            if lock
            else self._lessons.require_by_id(identifier)
        )
        lesson.require_owner(owner_id)
        return lesson

    def _save(
        self, before: StandaloneLesson, updated: StandaloneLesson
    ) -> StandaloneLessonResponse:
        with self._uow:
            current = self._load(str(before.content.id), str(before.owner_id), lock=True)
            if without_lesson_image(current) != without_lesson_image(before):
                raise CourseConflict("Lesson changed during generation; reload and retry")
            updated = replace(
                updated,
                content=replace(
                    updated.content, image=current.content.image or updated.content.image
                ),
            )
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)


class CreateStandaloneLesson(_StandaloneUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        ids: IdGenerator,
    ) -> None:
        super().__init__(lessons, uow)
        self._ids = ids

    def execute(self, request: CreateStandaloneLessonRequest) -> StandaloneLessonResponse:
        title, description = lesson_details(request.title, request.description)
        lesson = StandaloneLesson(
            LessonOwnerId(request.owner_id),
            description,
            Lesson(LessonId.new(self._ids), title, (title,), request.minutes),
            flow=request.flow,
        )
        style = requested_style(request.style) if request.style is not None else None
        lesson = replace(lesson, content=replace(lesson.content, style=style))
        with self._uow:
            self._lessons.add(lesson)
            self._uow.commit()
        return standalone_response(lesson)


class GetStandaloneLesson(_StandaloneUseCase):
    def execute(self, request: StandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            return standalone_response(self._load(request.lesson_id, request.owner_id))


class UpdateStandaloneLesson(_StandaloneUseCase):
    def execute(self, request: UpdateStandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id, lock=True)
            before.require_revision(request.expected_revision)
            title, description = lesson_details(request.title, request.description)
            style = draft_style(
                request.style,
                before.content.style,
                (title, description, request.minutes)
                != (before.content.title, before.description, before.content.minutes),
            )
            updated = before.update_details(
                title, description, request.minutes, style, request.flow
            )
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)


class ListStandaloneLessons(_StandaloneUseCase):
    def execute(self, request: ListStandaloneLessonsRequest) -> ListStandaloneLessonsResponse:
        if not 1 <= request.limit <= 100 or request.offset < 0:
            raise CourseError("Invalid lesson pagination")
        with self._uow:
            lessons = self._lessons.list_by_owner(
                LessonOwnerId(request.owner_id), request.limit, request.offset
            )
            return ListStandaloneLessonsResponse(tuple(standalone_response(ls) for ls in lessons))


class PlanStandaloneLesson(_StandaloneUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        agent: LessonAgent,
        tracking: UsageTracking | None = None,
        style_planner: StylePlanner | None = None,
        voices: VoiceCatalog | None = None,
        thumbnails: ThumbnailGenerator | None = None,
        memories: GuideRepository | None = None,
        thumbnail_jobs: ThumbnailJobs | None = None,
    ) -> None:
        super().__init__(lessons, uow)
        self._memories = memories
        self._agent = agent
        self._style_planner, self._voices = style_planner, voices
        self._tracking = tracking
        self._thumbnails = thumbnails
        self._thumbnail_jobs = thumbnail_jobs

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id)
            before.require_revision(request.expected_revision)
            if len(before.turns) >= 50:
                raise CourseConflict("Lesson conversation limit reached")
            memory_notes = load_memory_guidance(self._memories, request.owner_id, request.lesson_id)
            message = request.message or before.description
            text(message, 2000)
        if self._thumbnail_jobs and not before.content.image:
            self._thumbnail_jobs.enqueue(ThumbnailJob(request.lesson_id, request.owner_id))
        # Inline generators remain useful to callers without a background dispatcher.
        if not before.content.image:
            image = initial_thumbnail(
                self._thumbnails,
                self._tracking,
                before.content.title,
                before.description,
                before.content.topics,
                style=before.content.style,
                lesson_id=request.lesson_id,
            )
            if image:
                illustrated = replace(
                    before,
                    content=replace(before.content, image=image),
                    revision=before.revision + 1,
                )
                self._save(before, illustrated)
                before = illustrated
        working = before
        if self._style_planner and (
            before.content.style is None or not before.content.style.resolved
        ):
            preferences = before.content.style
            from app.courses.application.style_dto import style_input

            style = resolve_style(
                before.description,
                style_input(preferences) if preferences else None,
                request.generation_mode,
                self._style_planner,
                self._voices,
                tracking=self._tracking,
                lesson_id=request.lesson_id,
            )
            working = replace(before, content=replace(before.content, style=style))
        with (
            self._tracking.scope(None, request.lesson_id, "lesson")
            if self._tracking
            else nullcontext()
        ):
            result = self._agent.run(
                LessonAgentRequest(
                    before.content.title,
                    before.brief(),
                    guide_with_memories(working.guide(), memory_notes),
                    before.chapter(),
                    None,
                    None,
                    description=before.description,
                    previous_plan=before.content.plan,
                    conversation=tuple((t.user, t.assistant) for t in before.turns),
                    message=message,
                    generation_mode=request.generation_mode,
                    session=AgentSessionContext(
                        request.owner_id, request.lesson_id, request.job_id, request.session_id
                    ),
                )
            )
        updated = working.revise(
            message,
            result.plan,
            PlanGeneration(
                result.model,
                result.requests,
                result.tool_calls,
                result.total_tokens,
                result.session_id,
            ),
        )
        return self._save(before, updated)


class ApproveStandaloneLesson(_StandaloneUseCase):
    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id, lock=True)
            before.require_revision(request.expected_revision)
            updated = before if before.approved else before.approve()
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)
