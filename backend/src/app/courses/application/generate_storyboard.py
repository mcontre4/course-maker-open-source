import hashlib
import json
from contextlib import nullcontext
from dataclasses import asdict, dataclass

from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.guide_memory import guide_with_memories, load_memory_guidance
from app.courses.application.thumbnail_merge import without_course_images
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import CourseId
from app.courses.domain.storyboard import StoryboardGeneration
from app.courses.domain.validation import text
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.guide import GuideRepository
from app.courses.ports.spend import UsageTracking
from app.courses.ports.storyboard_agent import (
    STORYBOARD_PROMPT_VERSION,
    StoryboardAgent,
    StoryboardAgentRequest,
)
from app.courses.ports.syllabus_agent import SyllabusConversations
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GenerateStoryboardRequest:
    course_id: str
    lesson_id: str
    visual_style: str | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    session_id: str | None = None
    script_session_id: str | None = None
    job_id: str | None = None
    message: str = ""
    owner_id: str | None = None


def artifact_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_canonical_artifact(value), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _canonical_artifact(value: object) -> object:
    if isinstance(value, dict):
        # New optional continuity fields must not invalidate legacy narration hashes.
        scene = "scene_id" in value and "narration_text" in value
        additions = {
            "object_ids",
            "opening_composition",
            "closing_composition",
            "camera",
            "continuity_from_previous",
        }
        cue = "anchor_text" in value and "action" in value
        cue_additions = {"focus", "relationship", "hold"}
        return {
            key: _canonical_artifact(item)
            for key, item in value.items()
            if not (not item and (scene and key in additions or cue and key in cue_additions))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical_artifact(item) for item in value]
    return value


class GenerateStoryboard:
    def __init__(
        self,
        courses: CourseRepository,
        conversations: SyllabusConversations,
        agent: StoryboardAgent,
        uow: UnitOfWork,
        tracking: UsageTracking | None = None,
        memories: GuideRepository | None = None,
    ) -> None:
        self._memories = memories
        self._tracking = tracking
        self._courses, self._conversations = courses, conversations
        self._agent, self._uow = agent, uow

    def execute(self, request: GenerateStoryboardRequest) -> CourseResponse:
        if request.visual_style is not None:
            text(request.visual_style, 4000)
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
                raise CourseConflict("Approve the syllabus before generating storyboards")
            lesson = before.lesson(request.lesson_id)
            style = lesson.style or before.style
            visual_style = style.visual_direction() if style else request.visual_style
            if lesson.storyboard is not None and not (
                request.session_id or request.script_session_id or request.message
            ):
                if request.visual_style is not None and (
                    lesson.storyboard_generation is None
                    or visual_style != lesson.storyboard_generation.visual_style
                ):
                    raise CourseConflict(
                        "A storyboard already exists with different visual guidelines"
                    )
                return course_response(before)
            if request.lesson_id in before.reviewed:
                raise CourseConflict("A reviewed lesson cannot receive a new storyboard")
            if lesson.plan is None:
                raise CourseConflict("Generate the lesson plan before generating a storyboard")
            state = self._conversations.get_by_course_id(course_id)
            if state is None or state.curriculum is None:
                raise CourseConflict("A saved course guide is required to generate a storyboard")
        style = lesson.style or before.style
        visual_style = style.visual_direction() if style else request.visual_style
        agent_request = StoryboardAgentRequest(
            lesson.plan,
            guide_with_memories(
                style.apply_to_guide(state.curriculum.guide) if style else state.curriculum.guide,
                memory_notes,
            ),
            lesson.minutes,
            visual_style,
            generation_mode=request.generation_mode,
            visual_style_id=style.visual_style_id if style else "flat-vector-science",
            visual_style_version=style.visual_style_version if style else 1,
            session=AgentSessionContext(
                request.owner_id or before.owner_id or "",
                request.lesson_id,
                request.job_id,
                request.session_id,
            )
            if request.owner_id is not None or before.owner_id is not None
            else None,
            script_session_id=request.script_session_id,
            message=request.message,
        )
        with (
            self._tracking.scope(str(course_id), request.lesson_id, "storyboard")
            if self._tracking
            else nullcontext()
        ):
            result = self._agent.run(agent_request)
        result.storyboard.validate_plan(lesson.plan, lesson.minutes)
        generation = StoryboardGeneration(
            result.usage,
            artifact_hash(
                {"request": asdict(agent_request), "prompt_version": STORYBOARD_PROMPT_VERSION}
            ),
            artifact_hash(asdict(result.storyboard)),
            STORYBOARD_PROMPT_VERSION,
            visual_style,
            script_session_id=result.script_session_id,
        )
        with self._uow:
            current = self._courses.require_for_syllabus_change(course_id)
            if (
                without_course_images(current) != without_course_images(before)
                or self._conversations.get_by_course_id(course_id) != state
            ):
                raise CourseConflict(
                    "Course changed during storyboard generation; reload and retry"
                )
            updated = current.storyboard_lesson(request.lesson_id, result.storyboard, generation)
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)
