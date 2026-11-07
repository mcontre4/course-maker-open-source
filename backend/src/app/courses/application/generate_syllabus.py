from contextlib import nullcontext
from dataclasses import dataclass, replace

from app.courses.application.curriculum_dto import CurriculumResponse, curriculum_response
from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.guide_memory import load_memory_guidance
from app.courses.application.style_dto import style_input
from app.courses.application.style_resolution import resolve_style
from app.courses.application.thumbnail_merge import with_course_images, without_course_images
from app.courses.domain.course import Course
from app.courses.domain.curriculum import Curriculum
from app.courses.domain.curriculum_revision import revise_curriculum
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import ChapterId, CourseId, LessonId
from app.courses.domain.validation import text
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.guide import GuideRepository
from app.courses.ports.spend import UsageTracking
from app.courses.ports.style import StylePlanner, VoiceCatalog
from app.courses.ports.syllabus_agent import (
    ConversationTurn,
    SyllabusAgent,
    SyllabusAgentRequest,
    SyllabusChapterContext,
    SyllabusConversation,
    SyllabusConversations,
    SyllabusCourseContext,
    SyllabusLessonContext,
)
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class GenerateSyllabusRequest:
    course_id: str
    message: str
    expected_revision: int | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session_id: str | None = None
    owner_id: str | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class SyllabusSessionRequest:
    course_id: str
    owner_id: str | None = None


@dataclass(frozen=True)
class SyllabusSessionResponse:
    session_id: str
    revision: int
    turns: tuple[ConversationTurn, ...]
    curriculum: CurriculumResponse | None


@dataclass(frozen=True)
class GenerateSyllabusResponse:
    course: CourseResponse
    session: SyllabusSessionResponse
    message: str


def session_response(state: SyllabusConversation) -> SyllabusSessionResponse:
    return SyllabusSessionResponse(
        state.agent_session_id or state.course_id,
        state.revision,
        state.turns,
        curriculum_response(state.curriculum),
    )


def _normalize_identifiers(course: Course, plan: Curriculum, ids: IdGenerator) -> Curriculum:
    """Preserve existing persisted IDs; allocate IDs for new model-local identifiers."""
    chapter_ids = {str(ch.id) for ch in course.chapters}
    chapter_mapping = {
        ch.chapter_id: ch.chapter_id if ch.chapter_id in chapter_ids else str(ChapterId.new(ids))
        for ch in plan.chapters
    }
    lessons = {str(ls.id): ls for ch in course.chapters for ls in ch.lessons}
    mapping = {
        ls.lesson_id: ls.lesson_id if ls.lesson_id in lessons else str(LessonId.new(ids))
        for ch in plan.chapters
        for ls in ch.lessons
    }
    chapters = tuple(
        replace(
            ch,
            chapter_id=chapter_mapping[ch.chapter_id],
            lessons=tuple(
                replace(
                    ls,
                    lesson_id=mapping[ls.lesson_id],
                    chapter_id=chapter_mapping[ch.chapter_id],
                    prerequisites=tuple(mapping[key] for key in ls.prerequisites),
                )
                for ls in ch.lessons
            ),
        )
        for ch in plan.chapters
    )
    normalized = replace(
        plan,
        chapters=chapters,
        required_topic_coverage=tuple(
            replace(item, lesson_ids=tuple(mapping[key] for key in item.lesson_ids))
            for item in plan.required_topic_coverage
        ),
    )
    return normalized


class GenerateSyllabus:
    def __init__(
        self,
        courses: CourseRepository,
        conversations: SyllabusConversations,
        agent: SyllabusAgent,
        uow: UnitOfWork,
        ids: IdGenerator,
        tracking: UsageTracking | None = None,
        style_planner: StylePlanner | None = None,
        voices: VoiceCatalog | None = None,
        memories: GuideRepository | None = None,
    ) -> None:
        self._memories = memories
        self._tracking = tracking
        self._style_planner, self._voices = style_planner, voices
        self._courses, self._conversations, self._agent = courses, conversations, agent
        self._uow, self._ids = uow, ids

    def execute(self, request: GenerateSyllabusRequest) -> GenerateSyllabusResponse:
        text(request.message, 20000)
        course_id = CourseId(request.course_id)
        # Close the read snapshot before invoking either external API.
        with self._uow:
            before = self._courses.require_by_id(course_id)
            if (
                before.owner_id is not None
                and request.owner_id is not None
                and request.owner_id != before.owner_id
            ):
                raise CourseNotFound("Course not found")
            memory_notes = load_memory_guidance(self._memories, before.owner_id, request.course_id)
            before.require_draft()
            state = self._conversations.get_by_course_id(course_id) or SyllabusConversation(
                str(course_id)
            )
        if request.expected_revision is not None and request.expected_revision != state.revision:
            raise CourseConflict(
                "Syllabus conversation changed; reload before sending this message"
            )
        working = before
        if self._style_planner and (before.style is None or not before.style.resolved):
            preferences = before.style
            style = resolve_style(
                before.description,
                style_input(preferences) if preferences else None,
                request.generation_mode,
                self._style_planner,
                self._voices,
                tracking=self._tracking,
                course_id=str(course_id),
            )
            working = replace(before, style=style)
        context = SyllabusCourseContext(
            before.title,
            before.description
            + (
                "\nRemembered preferences (current settings take precedence):\n"
                + "\n".join(memory_notes)
                if memory_notes
                else ""
            )
            + ("\nPresentation style: " + working.style.directions() if working.style else ""),
            before.duration,
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
                for ch in before.chapters
            ),
        )
        with (
            self._tracking.scope(str(course_id), None, "syllabus")
            if self._tracking
            else nullcontext()
        ):
            result = self._agent.run(
                SyllabusAgentRequest(
                    request.message,
                    state.history_json,
                    context,
                    state.curriculum,
                    generation_mode=request.generation_mode,
                    session=AgentSessionContext(
                        request.owner_id or before.owner_id or "",
                        request.course_id,
                        request.job_id,
                        request.session_id,
                    )
                    if request.owner_id is not None or before.owner_id is not None
                    else None,
                )
            )
        updated, plan = working, state.curriculum
        if result.curriculum is not None:
            result.curriculum.validate_budget(before.duration)
            plan = _normalize_identifiers(before, result.curriculum, self._ids)
            updated = revise_curriculum(working, plan, state.curriculum)
        next_state = replace(
            state,
            revision=state.revision + 1,
            history_json=result.history_json,
            curriculum=plan,
            turns=(*state.turns, ConversationTurn(request.message, result.message)),
            agent_session_id=result.session_id,
        )
        with self._uow:
            current = self._courses.require_for_syllabus_change(course_id)
            current.require_draft()
            if without_course_images(current) != without_course_images(before):
                raise CourseConflict("Course changed during generation; reload and retry")
            updated = with_course_images(updated, current)
            self._conversations.save(next_state, expected_revision=state.revision)
            if updated != before:
                self._courses.save(updated)
            self._uow.commit()
        return GenerateSyllabusResponse(
            course_response(updated), session_response(next_state), result.message
        )


class GetSyllabusSession:
    def __init__(
        self, courses: CourseRepository, conversations: SyllabusConversations, uow: UnitOfWork
    ) -> None:
        self._courses, self._conversations, self._uow = courses, conversations, uow

    def execute(self, request: SyllabusSessionRequest) -> SyllabusSessionResponse:
        course_id = CourseId(request.course_id)
        with self._uow:
            course = self._courses.require_by_id(course_id)
            if (
                course.owner_id is not None
                and request.owner_id is not None
                and course.owner_id != request.owner_id
            ):
                raise CourseNotFound("Course not found")
            state = self._conversations.get_by_course_id(course_id)
        return session_response(state or SyllabusConversation(str(course_id)))
