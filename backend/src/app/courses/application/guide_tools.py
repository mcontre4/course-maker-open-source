import json
from dataclasses import asdict, dataclass, field, replace
from difflib import unified_diff

from app.courses.application.generate_syllabus import _normalize_identifiers
from app.courses.application.guide_context import GuideDependencies, GuideResource
from app.courses.domain.curriculum import Curriculum
from app.courses.domain.curriculum_revision import revise_curriculum
from app.courses.domain.errors import CourseConflict, CourseError
from app.courses.domain.generation import GenerationMode
from app.courses.domain.guide import GuideMemory, GuideMemoryId, GuideThread, GuideTurn
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.validation import text
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.guide import GuideToolRequest, GuideToolResponse
from app.courses.ports.lesson_agent import LessonAgentRequest
from app.courses.ports.syllabus_agent import (
    SyllabusAgentRequest,
    SyllabusChapterContext,
    SyllabusCourseContext,
    SyllabusLessonContext,
)


@dataclass
class GuideChanges:
    resource: GuideResource
    memories: list[GuideMemory] = field(default_factory=list)
    deleted_memories: set[str] = field(default_factory=set)
    outline_changed: bool = False
    syllabus_session_changed: bool = False
    description: str = ""


class ExecuteGuideTool:
    """Tools read through ports and stage mutations for the message's atomic commit."""

    def __init__(
        self,
        dependencies: GuideDependencies,
        thread: GuideThread,
        changes: GuideChanges,
        source_message_id: str,
        turns: tuple[GuideTurn, ...],
        mode: GenerationMode,
    ) -> None:
        self._d, self._thread, self._changes = dependencies, thread, changes
        self._source, self._turns, self._mode = source_message_id, turns, mode

    def execute(self, request: GuideToolRequest) -> GuideToolResponse:
        operation = request.operation
        if operation == "get_lesson_artifact":
            resource = self._changes.resource
            if resource.lesson:
                lesson = resource.lesson.content
            else:
                assert resource.course is not None
                if not request.text:
                    raise CourseError("Choose a lesson ID from the current course")
                lesson = resource.course.lesson(request.text)
            artifacts = {
                "outline": lesson.plan,
                "script": lesson.storyboard,
                "animation": lesson.animation,
                "style": lesson.style,
            }
            if request.key not in artifacts:
                raise CourseError("Choose outline, script, animation, or style")
            artifact = artifacts[request.key]
            return GuideToolResponse(
                json.dumps(asdict(artifact))
                if artifact is not None
                else "This artifact has not been generated yet."
            )
        if operation == "revise_outline":
            return self._revise(request.text)
        if operation == "remember":
            return self._remember(request)
        if operation == "forget_memory":
            return self._forget(request)
        if operation == "restore_outline_version":
            self._require_change_available()
            with self._d.uow:
                version = self._d.repository.require_version(
                    self._thread.resource_id, request.revision
                )
            if self._changes.resource.lesson:
                self._apply_plan(self._d.codec.decode_plan(version.outline_json))
            else:
                self._apply_curriculum(self._d.codec.decode_curriculum(version.outline_json))
            self._changes.description = f"Restored outline version {request.revision}"
            return GuideToolResponse("Outline restored as a new version; approval reset.")
        with self._d.uow:
            if operation == "list_outline_versions":
                versions = self._d.repository.list_versions(
                    self._thread.resource_id, 50, request.revision or None
                )
                return GuideToolResponse(
                    json.dumps(
                        [
                            {
                                "revision": v.revision,
                                "description": v.description,
                                "created_at": v.created_at,
                            }
                            for v in versions
                        ]
                    )
                )
            if operation in ("get_outline_version", "compare_outline_versions"):
                version = self._d.repository.require_version(
                    self._thread.resource_id, request.revision
                )
                if operation == "get_outline_version":
                    return GuideToolResponse(version.outline_json)
                other = self._d.repository.require_version(
                    self._thread.resource_id, request.other_revision
                )
                left = json.dumps(json.loads(version.outline_json), indent=2).splitlines()
                right = json.dumps(json.loads(other.outline_json), indent=2).splitlines()
                return GuideToolResponse(
                    "\n".join(
                        unified_diff(
                            left,
                            right,
                            fromfile=str(request.revision),
                            tofile=str(request.other_revision),
                        )
                    )
                )
            if operation == "search_lesson_history":
                text(request.text, 200)
                turns = self._d.repository.search_history(
                    self._thread.owner_id, self._thread.resource_id, request.text
                )
                return GuideToolResponse(
                    json.dumps(
                        [
                            {
                                "thread_id": str(t.thread_id),
                                "message_id": str(t.id),
                                "user": t.user,
                                "assistant": t.assistant,
                            }
                            for t in turns
                        ]
                    )
                )
        raise CourseError("Unknown guide tool")

    def _require_change_available(self) -> None:
        if self._changes.outline_changed or self._changes.syllabus_session_changed:
            raise CourseConflict("An outline change is already staged for this message")

    def _apply_plan(self, plan: LessonPlan, generation: PlanGeneration | None = None) -> None:
        lesson = self._changes.resource.lesson
        assert lesson is not None
        self._changes.resource = replace(
            self._changes.resource, lesson=lesson.apply_guide_plan(plan, generation)
        )
        self._changes.outline_changed = True

    def _apply_curriculum(self, curriculum: Curriculum) -> None:
        resource = self._changes.resource
        assert resource.course is not None and resource.syllabus is not None
        resource.course.require_draft()
        curriculum.validate_budget(resource.course.duration)
        plan = _normalize_identifiers(resource.course, curriculum, self._d.ids)
        course = revise_curriculum(resource.course, plan, resource.syllabus.curriculum)
        self._changes.resource = replace(
            resource,
            course=course,
            syllabus=replace(
                resource.syllabus, curriculum=plan, revision=resource.syllabus.revision + 1
            ),
        )
        self._changes.outline_changed = True

    def _revise(self, instructions: str) -> GuideToolResponse:
        self._require_change_available()
        text(instructions, 20000)
        memories = [
            m.content
            for m in self._changes.memories
            if str(m.id) not in self._changes.deleted_memories
        ]
        instructions += "\nRelevant remembered context:\n" + "\n".join(memories)
        resource = self._changes.resource
        if resource.lesson:
            lesson = resource.lesson
            result = self._d.lesson_agent.run(
                LessonAgentRequest(
                    lesson.content.title,
                    lesson.brief(),
                    lesson.guide(),
                    lesson.chapter(),
                    None,
                    None,
                    description=lesson.description,
                    previous_plan=lesson.content.plan,
                    conversation=tuple((t.user, t.assistant) for t in self._turns[-12:]),
                    message=instructions,
                    generation_mode=self._mode,
                    session=AgentSessionContext(
                        self._thread.owner_id,
                        self._thread.resource_id,
                        session_id=lesson.content.plan_generation.session_id
                        if lesson.content.plan_generation
                        else None,
                    ),
                )
            )
            result.plan.validate_brief(
                str(lesson.content.id),
                lesson.brief().objectives,
                lesson.content.topics,
                lesson.content.minutes,
            )
            self._apply_plan(
                result.plan,
                PlanGeneration(
                    result.model,
                    result.requests,
                    result.tool_calls,
                    result.total_tokens,
                    result.session_id,
                ),
            )
            outline = asdict(result.plan)
        else:
            assert resource.course is not None and resource.syllabus is not None
            course = resource.course
            course.require_draft()
            context = SyllabusCourseContext(
                course.title,
                course.description
                + ("\nPresentation style: " + course.style.directions() if course.style else ""),
                course.duration,
                tuple(
                    SyllabusChapterContext(
                        str(ch.id),
                        ch.title,
                        ch.summary,
                        tuple(
                            SyllabusLessonContext(str(ls.id), ls.title, ls.topics, ls.minutes)
                            for ls in ch.lessons
                        ),
                    )
                    for ch in course.chapters
                ),
            )
            response = self._d.syllabus_agent.run(
                SyllabusAgentRequest(
                    instructions,
                    "[]",
                    context,
                    resource.syllabus.curriculum,
                    generation_mode=self._mode,
                    session=AgentSessionContext(
                        self._thread.owner_id,
                        self._thread.resource_id,
                        session_id=resource.syllabus.agent_session_id,
                    ),
                )
            )
            if response.curriculum is not None:
                self._apply_curriculum(response.curriculum)
            else:
                self._changes.resource = replace(
                    self._changes.resource,
                    syllabus=replace(resource.syllabus, revision=resource.syllabus.revision + 1),
                )
            assert self._changes.resource.syllabus is not None
            self._changes.resource = replace(
                self._changes.resource,
                syllabus=replace(
                    self._changes.resource.syllabus,
                    agent_session_id=response.session_id,
                    history_json=response.history_json,
                ),
            )
            self._changes.syllabus_session_changed = True
            if response.curriculum is None:
                return GuideToolResponse(response.message)
            outline = asdict(response.curriculum)
        self._changes.description = instructions.split("\nRelevant remembered context:")[0][:2000]
        return GuideToolResponse(
            json.dumps({"status": "Outline updated; approval reset", "outline": outline})
        )

    def _remember(self, request: GuideToolRequest) -> GuideToolResponse:
        if request.scope not in ("user", "lesson"):
            raise CourseError("Memory scope must be user or lesson")
        resource_id = "" if request.scope == "user" else self._thread.resource_id
        existing = next(
            (
                m
                for m in self._changes.memories
                if m.resource_id == resource_id and m.key == request.key
            ),
            None,
        )
        if existing:
            updated = existing.correct(request.text, self._source)
            self._changes.memories[self._changes.memories.index(existing)] = updated
        else:
            updated = GuideMemory(
                GuideMemoryId.new(self._d.ids),
                self._thread.owner_id,
                resource_id,
                request.key,
                request.text,
                self._source,
            )
            self._changes.memories.append(updated)
        self._changes.deleted_memories.discard(str(updated.id))
        return GuideToolResponse("Memory saved for " + request.scope)

    def _forget(self, request: GuideToolRequest) -> GuideToolResponse:
        if request.scope not in ("user", "lesson"):
            raise CourseError("Memory scope must be user or lesson")
        resource_id = "" if request.scope == "user" else self._thread.resource_id
        for memory in self._changes.memories:
            if memory.key == request.key and memory.resource_id == resource_id:
                self._changes.deleted_memories.add(str(memory.id))
        return GuideToolResponse(
            "Memory forgotten. Historical messages remain in the chat archive."
        )
