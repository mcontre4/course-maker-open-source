import json
from contextlib import nullcontext
from dataclasses import asdict

from app.courses.application.guide_context import _GuideUseCase, thread_response
from app.courses.application.guide_dto import GuideThreadResponse, SendGuideMessageRequest
from app.courses.application.guide_tools import ExecuteGuideTool, GuideChanges
from app.courses.domain.errors import CourseConflict
from app.courses.domain.guide import GuideMessageId, GuideTurn, OutlineVersion
from app.courses.domain.validation import text
from app.courses.ports.guide import GuideAgentRequest


class SendGuideMessage(_GuideUseCase):
    def execute(self, request: SendGuideMessageRequest) -> GuideThreadResponse:
        text(request.message, 20000)
        with self._d.uow:
            thread = self._thread(request.thread_id, request.owner_id)
            existing = self._d.repository.get_by_request_id(thread.id, request.request_id)
            if existing:
                if existing.user != request.message:
                    raise CourseConflict("Request ID already used for a different message")
                saved_turns = self._d.repository.list_turns(thread.id, limit=101)
                return thread_response(thread, saved_turns[-100:], len(saved_turns) > 100)
            thread.require_revision(request.expected_revision)
            before = self._resource(thread.resource_id, request.owner_id)
            turns = self._d.repository.list_turns(thread.id, limit=100)
            memories = self._d.repository.list_memories(request.owner_id, thread.resource_id)
        source = str(GuideMessageId.new(self._d.ids))
        changes = GuideChanges(before, list(memories))
        tool = ExecuteGuideTool(self._d, thread, changes, source, turns, request.generation_mode)
        context = {
            "guide": thread.guide,
            "current_state": json.loads(before._context_json()),
            "memories": [
                {"scope": "lesson" if m.resource_id else "user", "key": m.key, "content": m.content}
                for m in memories
            ],
            "previous_messages": [{"user": t.user, "assistant": t.assistant} for t in turns]
            if not thread.history_json
            else [],
            "summary": thread.summary,
        }
        with (
            self._d.tracking.scope(
                thread.resource_id if before.course else None,
                thread.resource_id if before.lesson else None,
                "guide",
            )
            if self._d.tracking
            else nullcontext()
        ):
            result = self._d.agent.run(
                GuideAgentRequest(
                    request.message,
                    json.dumps(context),
                    thread.history_json,
                    thread.summary,
                    request.generation_mode,
                ),
                tool.execute,
            )
        updated_thread = thread.advance(result.history_json, result.summary, request.message)
        turn = GuideTurn(
            GuideMessageId(source),
            thread.id,
            updated_thread.revision,
            request.request_id,
            request.message,
            result.message,
            result.tool_history_json,
        )
        with self._d.uow:
            # Lock the resource first, in the same order as thread creation and manual edits.
            current = self._resource(thread.resource_id, request.owner_id, lock=True)
            if current._without_thumbnails() != before._without_thumbnails():
                raise CourseConflict(
                    "Lesson changed while the guide was responding; reload and retry"
                )
            self._d.repository.save(updated_thread, expected_revision=thread.revision)
            self._d.repository.add_turn(turn)
            if changes.outline_changed:
                changes.resource = changes.resource._with_thumbnails(current)
                if changes.resource.lesson:
                    self._d.lessons.save(changes.resource.lesson)
                    revision = changes.resource.lesson.revision
                else:
                    assert (
                        changes.resource.course is not None
                        and changes.resource.syllabus is not None
                    )
                    assert before.syllabus is not None
                    self._d.courses.save(changes.resource.course)
                    self._d.syllabuses.save(changes.resource.syllabus, before.syllabus.revision)
                    revision = changes.resource.syllabus.revision
                outline = (
                    changes.resource.lesson.content.plan
                    if changes.resource.lesson
                    else changes.resource.syllabus.curriculum
                    if changes.resource.syllabus
                    else None
                )
                assert outline is not None
                self._d.repository.add_version(
                    OutlineVersion(
                        thread.resource_id,
                        revision,
                        json.dumps(asdict(outline)),
                        changes.description,
                        source,
                    )
                )
            if changes.syllabus_session_changed and not changes.outline_changed:
                assert changes.resource.syllabus is not None and before.syllabus is not None
                self._d.syllabuses.save(changes.resource.syllabus, before.syllabus.revision)
            originals = {str(m.id): m for m in memories}
            for memory in changes.memories:
                original = originals.get(str(memory.id))
                if str(memory.id) in changes.deleted_memories:
                    if original:
                        self._d.repository.delete_memory(
                            request.owner_id, str(memory.id), original.revision
                        )
                elif memory != original:
                    self._d.repository.save_memory(memory, original.revision if original else 0)
            self._d.uow.commit()
        return thread_response(updated_thread, (*turns[-99:], turn), len(turns) >= 100)
