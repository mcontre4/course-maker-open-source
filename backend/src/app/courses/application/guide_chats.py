from dataclasses import replace

from app.courses.application.guide_context import _GuideUseCase, thread_response
from app.courses.application.guide_dto import (
    ChangeGuideMemoryRequest,
    CreateGuideThreadRequest,
    GuideMemoriesResponse,
    GuideMemoryResponse,
    GuideScopeRequest,
    GuideThreadRequest,
    GuideThreadResponse,
    GuideThreadsResponse,
    OutlineVersionResponse,
    OutlineVersionsRequest,
    OutlineVersionsResponse,
)
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.guide import GuideMessageId, GuideThread, GuideThreadId, GuideTurn


class CreateGuideThread(_GuideUseCase):
    def execute(self, request: CreateGuideThreadRequest) -> GuideThreadResponse:
        with self._d.uow:
            resource = self._resource(request.resource_id, request.owner_id, lock=True)
            existing = self._d.repository.list_threads(
                request.owner_id, request.resource_id, request.guide
            )
            thread = GuideThread(
                GuideThreadId.new(self._d.ids),
                request.owner_id,
                request.resource_id,
                request.guide,
                request.title,
            )
            if (
                not existing
                and request.guide == "syllabus"
                and resource.syllabus
                and resource.syllabus.history_json != "[]"
                and resource.syllabus.agent_session_id is None
            ):
                thread = replace(thread, history_json=resource.syllabus.history_json)
            self._d.repository.add(thread)
            # Import the pre-thread conversation only once. New chats remain independent.
            legacy = (
                tuple((t.user, t.assistant) for t in resource.lesson.turns)
                if resource.lesson
                else tuple((t.user, t.assistant) for t in resource.syllabus.turns)
                if resource.syllabus
                else ()
            )
            turns: list[GuideTurn] = []
            native_session = (
                resource.lesson.content.plan_generation.session_id
                if resource.lesson and resource.lesson.content.plan_generation
                else resource.syllabus.agent_session_id
                if resource.syllabus
                else None
            )
            if not existing and request.guide in ("lesson", "syllabus") and not native_session:
                for index, item in enumerate(legacy, 1):
                    turn = GuideTurn(
                        GuideMessageId.new(self._d.ids),
                        thread.id,
                        index,
                        f"legacy-{index}",
                        item[0],
                        item[1],
                    )
                    self._d.repository.add_turn(turn)
                    turns.append(turn)
                if turns:
                    thread = replace(thread, revision=len(turns))
                    self._d.repository.save(thread, expected_revision=0)
            self._d.uow.commit()
        return thread_response(thread, tuple(turns[-100:]), len(turns) > 100)


class ListGuideThreads(_GuideUseCase):
    def execute(self, request: GuideScopeRequest) -> GuideThreadsResponse:
        with self._d.uow:
            self._resource(request.resource_id, request.owner_id)
            threads = self._d.repository.list_threads(
                request.owner_id, request.resource_id, request.guide
            )
        return GuideThreadsResponse(tuple(thread_response(t) for t in threads))


class GetGuideThread(_GuideUseCase):
    def execute(self, request: GuideThreadRequest) -> GuideThreadResponse:
        with self._d.uow:
            thread = self._thread(request.thread_id, request.owner_id)
            turns = self._d.repository.list_turns(thread.id, request.before, 101)
        return thread_response(thread, turns[-100:], len(turns) > 100)


class ListGuideMemories(_GuideUseCase):
    def execute(self, request: GuideScopeRequest) -> GuideMemoriesResponse:
        with self._d.uow:
            self._resource(request.resource_id, request.owner_id)
            memories = self._d.repository.list_memories(request.owner_id, request.resource_id)
        return GuideMemoriesResponse(
            tuple(
                GuideMemoryResponse(
                    str(m.id),
                    "user" if not m.resource_id else "lesson",
                    m.key,
                    m.content,
                    m.source_message_id,
                    m.revision,
                )
                for m in memories
            )
        )


class ChangeGuideMemory(_GuideUseCase):
    def execute(self, request: ChangeGuideMemoryRequest) -> GuideMemoriesResponse:
        with self._d.uow:
            self._resource(request.resource_id, request.owner_id)
            memory = next(
                (
                    m
                    for m in self._d.repository.list_memories(request.owner_id, request.resource_id)
                    if str(m.id) == request.memory_id
                ),
                None,
            )
            if memory is None:
                raise CourseNotFound("Memory not found")
            if request.delete:
                self._d.repository.delete_memory(
                    request.owner_id, request.memory_id, request.expected_revision
                )
            else:
                self._d.repository.save_memory(
                    memory.correct(request.content, ""), request.expected_revision
                )
            self._d.uow.commit()
        return ListGuideMemories(self._d).execute(
            GuideScopeRequest(request.owner_id, request.resource_id)
        )


class ListOutlineVersions(_GuideUseCase):
    def execute(self, request: OutlineVersionsRequest) -> OutlineVersionsResponse:
        with self._d.uow:
            self._resource(request.resource_id, request.owner_id)
            versions = self._d.repository.list_versions(request.resource_id, 50, request.before)
        return OutlineVersionsResponse(
            tuple(
                OutlineVersionResponse(
                    v.revision,
                    v.outline_json,
                    v.description,
                    v.source_message_id,
                    v.created_at,
                    v.parent_revision,
                )
                for v in versions
            )
        )
