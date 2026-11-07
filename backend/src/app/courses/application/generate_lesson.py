from contextlib import nullcontext
from dataclasses import dataclass, replace

from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.guide_memory import guide_with_memories, load_memory_guidance
from app.courses.application.thumbnail_merge import without_course_images
from app.courses.application.thumbnails import initial_thumbnail
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import CourseId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.guide import GuideRepository
from app.courses.ports.lesson_agent import LessonAgent, LessonAgentRequest
from app.courses.ports.spend import UsageTracking
from app.courses.ports.syllabus_agent import SyllabusConversations
from app.courses.ports.thumbnail_jobs import ThumbnailJob, ThumbnailJobs
from app.courses.ports.thumbnails import ThumbnailGenerator
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GenerateLessonRequest:
    course_id: str
    lesson_id: str | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session_id: str | None = None
    owner_id: str | None = None
    job_id: str | None = None
    message: str = ""


class GenerateLesson:
    def __init__(
        self,
        courses: CourseRepository,
        conversations: SyllabusConversations,
        agent: LessonAgent,
        uow: UnitOfWork,
        tracking: UsageTracking | None = None,
        thumbnails: ThumbnailGenerator | None = None,
        memories: GuideRepository | None = None,
        thumbnail_jobs: ThumbnailJobs | None = None,
    ) -> None:
        self._thumbnails = thumbnails
        self._thumbnail_jobs = thumbnail_jobs
        self._memories = memories
        self._tracking = tracking
        self._courses, self._conversations = courses, conversations
        self._agent, self._uow = agent, uow

    def execute(self, request: GenerateLessonRequest) -> CourseResponse:
        course_id = CourseId(request.course_id)
        with self._uow:
            before = self._courses.require_by_id(course_id)
            if (
                before.owner_id is not None
                and request.owner_id is not None
                and request.owner_id != before.owner_id
            ):
                raise CourseNotFound("Course not found")
            memory_notes = load_memory_guidance(self._memories, before.owner_id, request.course_id)
            if before.status != "ready":
                raise CourseConflict("Approve the syllabus before generating lesson plans")
            lessons = tuple(ls for ch in before.chapters for ls in ch.lessons)
            lesson = before.lesson(
                request.lesson_id if request.lesson_id is not None else str(lessons[0].id)
            )
            if lesson.plan is not None and not (request.session_id or request.message):
                return course_response(before)
            if str(lesson.id) in before.reviewed:
                raise CourseConflict("A reviewed lesson cannot receive a new teaching plan")
            state = self._conversations.get_by_course_id(course_id)
            if state is None or state.curriculum is None:
                raise CourseConflict(
                    "Generate a syllabus with a course guide before planning lessons"
                )
        if self._thumbnail_jobs and not lesson.image:
            self._thumbnail_jobs.enqueue(
                ThumbnailJob(str(course_id), course=True, lesson_id=str(lesson.id))
            )
        style = lesson.style or before.style
        curriculum = state.curriculum
        briefs = tuple(ls for ch in curriculum.chapters for ls in ch.lessons)
        index = next((i for i, ls in enumerate(briefs) if ls.lesson_id == str(lesson.id)), None)
        if index is None:
            raise CourseConflict("Lesson is missing from the curriculum; regenerate the syllabus")
        brief = replace(
            briefs[index], title=lesson.title, concepts=lesson.topics, video_minutes=lesson.minutes
        )
        chapter = next(ch for ch in curriculum.chapters if ch.chapter_id == brief.chapter_id)
        with (
            self._tracking.scope(str(course_id), str(lesson.id), "lesson")
            if self._tracking
            else nullcontext()
        ):
            result = self._agent.run(
                LessonAgentRequest(
                    before.title,
                    brief,
                    guide_with_memories(
                        style.apply_to_guide(curriculum.guide) if style else curriculum.guide,
                        memory_notes,
                    ),
                    chapter,
                    briefs[index - 1] if index else None,
                    briefs[index + 1] if index + 1 < len(briefs) else None,
                    generation_mode=request.generation_mode,
                    message=request.message,
                    previous_plan=lesson.plan,
                    session=AgentSessionContext(
                        request.owner_id or before.owner_id or "",
                        str(lesson.id),
                        request.job_id,
                        request.session_id,
                    )
                    if request.owner_id is not None or before.owner_id is not None
                    else None,
                )
            )
        result.plan.validate_brief(str(lesson.id), brief.objectives, lesson.topics, lesson.minutes)
        image = lesson.image or initial_thumbnail(
            self._thumbnails,
            self._tracking,
            lesson.title,
            before.description,
            lesson.topics,
            style=style,
            course_id=str(course_id),
            lesson_id=str(lesson.id),
        )
        with self._uow:
            current = self._courses.require_for_syllabus_change(course_id)
            current_state = self._conversations.get_by_course_id(course_id)
            if (
                without_course_images(current) != without_course_images(before)
                or current_state != state
            ):
                raise CourseConflict("Course changed during lesson generation; reload and retry")
            updated = current.plan_lesson(
                str(lesson.id),
                result.plan,
                PlanGeneration(
                    result.model,
                    result.requests,
                    result.tool_calls,
                    result.total_tokens,
                    result.session_id,
                ),
            )
            updated = updated._replace_lesson(
                replace(
                    updated.lesson(str(lesson.id)),
                    image=current.lesson(str(lesson.id)).image or image,
                )
            )
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)
