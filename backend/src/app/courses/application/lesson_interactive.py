from contextlib import nullcontext
from dataclasses import dataclass, replace

from app.courses.application.lesson_interactive_dto import (
    BuildInteractiveRequest,
    BuildInteractiveResponse,
    ChangeInteractiveRequest,
    CreateInteractiveRequest,
    DeletedInteractiveResponse,
    InteractiveRequest,
    InteractiveResponse,
    InteractivesResponse,
    LearnerInteractiveResponse,
    LessonInteractivesRequest,
    PublicInteractivesRequest,
    PublicInteractivesResponse,
    PublishInteractiveRequest,
    ReorderInteractivesRequest,
    RestoreInteractiveRequest,
    SaveInteractiveDetailsRequest,
    interactive_response,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import LessonId
from app.courses.domain.lesson_interactive import (
    MAX_INTERACTIVES,
    BuildStage,
    InteractiveDetails,
    InteractiveId,
    InteractiveLesson,
    LessonInteractive,
    interactive_text,
)
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.lesson_interactive import (
    InteractiveAgent,
    InteractiveAgentRequest,
    InteractiveGenerationUnavailable,
    InteractiveJob,
    InteractiveJobs,
    InteractiveLessons,
    LessonInteractives,
)
from app.courses.ports.spend import UsageTracking
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.clock import Clock
from app.shared.domain.id_generator import IdGenerator


class _InteractiveUseCase:
    def __init__(
        self,
        lessons: InteractiveLessons,
        interactives: LessonInteractives,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        jobs: InteractiveJobs | None = None,
    ) -> None:
        self._lessons, self._interactives, self._uow = lessons, interactives, uow
        self._clock, self._ids, self._jobs = clock, ids, jobs

    def _owner(self, request: LessonInteractivesRequest) -> InteractiveLesson:
        lesson = self._lessons.require_for_change(LessonId(request.lesson_id))
        lesson.require_owner(request.owner_id)
        return lesson

    def _get(self, lesson_id: str, identifier: str) -> LessonInteractive:
        item = self._interactives.get_by_id(InteractiveId(identifier))
        if item is None or str(item.lesson_id) != lesson_id:
            raise CourseNotFound("Interactive not found")
        return item

    def _recover(self, item: LessonInteractive) -> LessonInteractive:
        now = self._clock.now()
        recovered = item.expire_build(now.isoformat(), now.timestamp())
        if recovered != item:
            self._interactives.save(recovered)
        return recovered

    def _load(self, request: InteractiveRequest) -> LessonInteractive:
        self._owner(request)
        return self._recover(self._get(request.lesson_id, request.id))

    def _enqueue(self, item: LessonInteractive) -> InteractiveResponse:
        assert item.build is not None
        try:
            if self._jobs is None:
                raise RuntimeError("Interactive jobs are not configured")
            self._jobs.enqueue(InteractiveJob(str(item.lesson_id), str(item.id), item.build.token))
        except Exception:
            with self._uow:
                self._lessons.require_for_change(item.lesson_id)
                current = self._get(str(item.lesson_id), str(item.id))
                if current.build and current.build.token == item.build.token:
                    item = current.fail_build(
                        "The build could not be started. Please retry the build.",
                        self._clock.now().isoformat(),
                    )
                    self._interactives.save(item)
                    self._uow.commit()
        return interactive_response(item)


class ListLessonInteractives(_InteractiveUseCase):
    def execute(self, request: LessonInteractivesRequest) -> InteractivesResponse:
        # The short write boundary also recovers leases abandoned by a crashed worker.
        with self._uow:
            self._owner(request)
            items = tuple(
                self._recover(i)
                for i in self._interactives.list_by_lesson_id(LessonId(request.lesson_id))
            )
            self._uow.commit()
        return InteractivesResponse(tuple(interactive_response(i) for i in items))


class GetLessonInteractive(_InteractiveUseCase):
    def execute(self, request: InteractiveRequest) -> InteractiveResponse:
        with self._uow:
            item = self._load(request)
            self._uow.commit()
        return interactive_response(item)


class CreateLessonInteractive(_InteractiveUseCase):
    def execute(self, request: CreateInteractiveRequest) -> InteractiveResponse:
        brief = interactive_text(request.brief, 2000, "Description")
        with self._uow:
            lesson = self._owner(request)
            if len(self._interactives.list_by_lesson_id(lesson.content.id)) >= MAX_INTERACTIVES:
                raise CourseConflict("A lesson can have up to 10 interactives.")
            now = self._clock.now()
            item = LessonInteractive(
                InteractiveId.new(self._ids),
                lesson.content.id,
                brief,
                InteractiveDetails("New interactive"),
                now.isoformat(),
                now.isoformat(),
                generation_mode=request.generation_mode,
            ).start_build(brief, str(self._ids.new_uuid()), now.isoformat(), now.timestamp())
            self._interactives.add(item, lesson)
            self._uow.commit()
        return self._enqueue(item)


class ChangeLessonInteractive(_InteractiveUseCase):
    def execute(self, request: ChangeInteractiveRequest) -> InteractiveResponse:
        instruction = interactive_text(request.instruction, 1000, "Change instruction")
        with self._uow:
            item = self._load(request)
            item.require_revision(request.expected_revision)
            item = item.start_build(
                instruction,
                str(self._ids.new_uuid()),
                self._clock.now().isoformat(),
                self._clock.now().timestamp(),
            )
            self._interactives.save(item)
            self._uow.commit()
        return self._enqueue(item)


class RetryInteractiveBuild(_InteractiveUseCase):
    def execute(self, request: InteractiveRequest) -> InteractiveResponse:
        with self._uow:
            item = self._load(request)
            item.require_idle()
            if item.failure is None:
                raise CourseConflict("There is no failed build to retry.")
            item = item.start_build(
                item.failure.request,
                str(self._ids.new_uuid()),
                self._clock.now().isoformat(),
                self._clock.now().timestamp(),
            )
            self._interactives.save(item)
            self._uow.commit()
        return self._enqueue(item)


class CancelInteractiveBuild(_InteractiveUseCase):
    def execute(self, request: InteractiveRequest) -> InteractiveResponse:
        with self._uow:
            item = self._load(request).fail_build(
                "The build was cancelled. You can retry it when you are ready.",
                self._clock.now().isoformat(),
            )
            self._interactives.save(item)
            self._uow.commit()
        return interactive_response(item)


class SaveInteractiveDetails(_InteractiveUseCase):
    def execute(self, request: SaveInteractiveDetailsRequest) -> InteractiveResponse:
        details = InteractiveDetails(request.title, request.goal, request.prompts)
        with self._uow:
            item = self._load(request)
            item.require_revision(request.expected_revision)
            item = item.save_details(details, self._clock.now().isoformat())
            self._interactives.save(item)
            self._uow.commit()
        return interactive_response(item)


class RestoreInteractiveVersion(_InteractiveUseCase):
    def execute(self, request: RestoreInteractiveRequest) -> InteractiveResponse:
        with self._uow:
            item = self._load(request)
            item.require_revision(request.expected_revision)
            item = item.restore(request.version, self._clock.now().isoformat())
            self._interactives.save(item)
            self._uow.commit()
        return interactive_response(item)


class PublishInteractiveVersion(_InteractiveUseCase):
    def execute(self, request: PublishInteractiveRequest) -> InteractiveResponse:
        with self._uow:
            item = self._load(request).publish(request.version, self._clock.now().isoformat())
            self._interactives.save(item)
            self._uow.commit()
        return interactive_response(item)


class DeleteLessonInteractive(_InteractiveUseCase):
    def execute(self, request: InteractiveRequest) -> DeletedInteractiveResponse:
        with self._uow:
            self._interactives.delete(self._load(request))
            self._uow.commit()
        return DeletedInteractiveResponse()


class ReorderLessonInteractives(_InteractiveUseCase):
    def execute(self, request: ReorderInteractivesRequest) -> InteractivesResponse:
        with self._uow:
            self._owner(request)
            existing = {
                str(i.id): self._recover(i)
                for i in self._interactives.list_by_lesson_id(LessonId(request.lesson_id))
            }
            if len(request.ids) != len(existing) or set(request.ids) != set(existing):
                raise CourseError("Include every interactive exactly once when reordering.")
            self._interactives.reorder(
                LessonId(request.lesson_id), tuple(InteractiveId(i) for i in request.ids)
            )
            self._uow.commit()
        return InteractivesResponse(tuple(interactive_response(existing[i]) for i in request.ids))


class GetPublicLessonInteractives(_InteractiveUseCase):
    def execute(self, request: PublicInteractivesRequest) -> PublicInteractivesResponse:
        # Consistent snapshot of lesson visibility and its selected published pages.
        with self._uow:
            lesson = self._lessons.require_by_id(LessonId(request.lesson_id))
            if not lesson.content.is_published:
                raise CourseNotFound("Lesson not found")
            items = []
            for item in self._interactives.list_by_lesson_id(lesson.content.id):
                published = item.version(item.published_version)
                if published:
                    items.append(
                        LearnerInteractiveResponse(
                            str(item.id),
                            str(item.lesson_id),
                            published.number,
                            item.details.title,
                            item.details.goal,
                            item.details.prompts,
                            published.html,
                        )
                    )
        return PublicInteractivesResponse(tuple(items))


class BuildLessonInteractive(_InteractiveUseCase):
    def __init__(
        self,
        lessons: InteractiveLessons,
        interactives: LessonInteractives,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        agent: InteractiveAgent,
        tracking: UsageTracking | None = None,
    ) -> None:
        super().__init__(lessons, interactives, uow, clock, ids)
        self._agent, self._tracking = agent, tracking

    def _active(self, request: BuildInteractiveRequest) -> LessonInteractive | None:
        item = self._interactives.get_by_id(InteractiveId(request.id))
        if item is None or str(item.lesson_id) != request.lesson_id:
            return None
        item = self._recover(item)
        return item if item.build and item.build.token == request.token else None

    def _stage(self, request: BuildInteractiveRequest, stage: BuildStage) -> bool:
        with self._uow:
            self._lessons.require_for_change(LessonId(request.lesson_id))
            item = self._active(request)
            if item is None or item.build is None:
                self._uow.commit()
                return False
            self._interactives.save(replace(item, build=replace(item.build, stage=stage)))
            self._uow.commit()
        return True

    def execute(self, request: BuildInteractiveRequest) -> BuildInteractiveResponse:
        try:
            with self._uow:
                lesson = self._lessons.require_for_change(LessonId(request.lesson_id))
                item = self._active(request)
                if item is None or item.build is None or item.build.stage != "reading_lesson":
                    self._uow.commit()
                    return BuildInteractiveResponse(False)
                current = item.version(item.current_version)
                agent_request = InteractiveAgentRequest(
                    lesson.content.title,
                    lesson.description,
                    lesson.content.topics,
                    lesson.audience,
                    lesson.content.plan,
                    item.brief,
                    item.build.request,
                    current.html if current else None,
                    item.generation_mode,
                    session=AgentSessionContext(
                        lesson.owner_id,
                        request.lesson_id,
                        str(item.id),
                        current.session_id if current else None,
                    )
                    if lesson.owner_id is not None
                    else None,
                )
                self._interactives.save(replace(item, build=replace(item.build, stage="designing")))
                self._uow.commit()
            if not self._stage(request, "building"):
                return BuildInteractiveResponse(False)
            with (
                self._tracking.scope(lesson.course_id, request.lesson_id, "interactive")
                if self._tracking
                else nullcontext()
            ):
                page = self._agent.run(agent_request)
            if not self._stage(request, "checking"):
                return BuildInteractiveResponse(False)
            with self._uow:
                self._lessons.require_for_change(LessonId(request.lesson_id))
                latest = self._active(request)
                if latest is None:
                    self._uow.commit()
                    return BuildInteractiveResponse(False)
                self._interactives.save(latest.complete_build(page, self._clock.now().isoformat()))
                self._uow.commit()
            return BuildInteractiveResponse(True)
        except CourseNotFound:
            # The lesson or activity may have been deleted while the worker was running.
            return BuildInteractiveResponse(False)
        except Exception as exc:
            message = (
                str(exc)
                if isinstance(exc, (CourseError, InteractiveGenerationUnavailable))
                else (
                    "The interactive could not be built. Please try again. "
                    "Your saved versions are safe."
                )
            )
            try:
                with self._uow:
                    self._lessons.require_for_change(LessonId(request.lesson_id))
                    latest = self._active(request)
                    if latest:
                        self._interactives.save(
                            latest.fail_build(message, self._clock.now().isoformat())
                        )
                    self._uow.commit()
            except CourseNotFound:
                pass
            return BuildInteractiveResponse(False)


@dataclass(frozen=True)
class InteractiveServices:
    list: ListLessonInteractives
    get: GetLessonInteractive
    create: CreateLessonInteractive
    change: ChangeLessonInteractive
    retry: RetryInteractiveBuild
    cancel: CancelInteractiveBuild
    details: SaveInteractiveDetails
    restore: RestoreInteractiveVersion
    publish: PublishInteractiveVersion
    delete: DeleteLessonInteractive
    reorder: ReorderLessonInteractives
    public: GetPublicLessonInteractives
