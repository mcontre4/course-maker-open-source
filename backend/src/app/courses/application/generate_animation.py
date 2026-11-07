from contextlib import nullcontext
from dataclasses import asdict, dataclass, field, fields

from app.courses.application.dto import CourseResponse, course_response
from app.courses.application.generate_storyboard import artifact_hash
from app.courses.application.guide_memory import guide_with_memories, load_memory_guidance
from app.courses.application.thumbnail_merge import without_course_images
from app.courses.domain.animation import AnimationProject
from app.courses.domain.course import Course
from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import CourseId
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.animation_backend import AnimationBackend
from app.courses.ports.animator import AnimationInput, AnimationUnavailable, Animator
from app.courses.ports.animator_model import AnimatorModel
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.guide import GuideRepository
from app.courses.ports.speech import SpeechArtifacts
from app.courses.ports.spend import UsageTracking
from app.courses.ports.syllabus_agent import SyllabusConversations
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GenerateAnimationRequest:
    course_id: str
    lesson_id: str
    visual_style: str
    generation_mode: GenerationMode = GenerationMode.BALANCED
    animator_model: AnimatorModel | None = None
    prepare_elements: bool = field(default=False, kw_only=True)
    animation_backend: AnimationBackend = AnimationBackend.DIRECT
    session_id: str | None = None
    reviewer_session_id: str | None = None
    job_id: str | None = None
    owner_id: str | None = None
    message: str = ""


class GenerateAnimation:
    def __init__(
        self,
        courses: CourseRepository,
        conversations: SyllabusConversations,
        animator: Animator,
        speech: SpeechArtifacts,
        uow: UnitOfWork,
        tracking: UsageTracking | None = None,
        memories: GuideRepository | None = None,
    ) -> None:
        self._memories = memories
        self._tracking = tracking
        self._courses, self._conversations = courses, conversations
        self._animator, self._speech, self._uow = animator, speech, uow

    def execute(self, request: GenerateAnimationRequest) -> CourseResponse:
        if not request.visual_style.strip() or len(request.visual_style) > 4000:
            raise CourseConflict("Supply a visual style specification of 1–4000 characters")
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
            lesson = before.lesson(request.lesson_id)
            state = self._conversations.get_by_course_id(course_id)
            if (
                before.status != "ready"
                or lesson.plan is None
                or lesson.storyboard is None
                or lesson.alignment is None
                or state is None
                or state.curriculum is None
            ):
                raise CourseConflict(
                    "Approved guide, plan, storyboard and aligned audio are required"
                )
            if request.lesson_id in before.reviewed and (
                lesson.animation is None or lesson.animation.review_status != "pending"
            ):
                raise CourseConflict("Reviewed lessons cannot receive new animation")
        style = lesson.style or before.style
        lesson.storyboard.validate_plan(lesson.plan, lesson.minutes)
        lesson.alignment.validate_storyboard(lesson.storyboard)
        if lesson.alignment.storyboard_hash != artifact_hash(asdict(lesson.storyboard)):
            raise CourseConflict("Storyboard changed after speech alignment")
        # No database transaction remains open while reading media or calling the animation model.
        audio = []
        for scene in lesson.alignment.scenes:
            content = self._speech.read(scene.audio_key)
            if content is None:
                raise AnimationUnavailable("Aligned audio is missing")
            audio.append(content)

        def source_ready(project: AnimationProject) -> None:
            nonlocal before
            if project.lesson_id != request.lesson_id:
                raise AnimationUnavailable("Animator returned another lesson")
            with self._uow:
                current = self._courses.require_for_syllabus_change(course_id)
                if (
                    not _same_content(current, before)
                    or self._conversations.get_by_course_id(course_id) != state
                ):
                    raise CourseConflict("Course changed during animation; reload and retry")
                before = current.animate_lesson(request.lesson_id, project)
                self._courses.save(before)
                self._uow.commit()

        with (
            self._tracking.scope(str(course_id), request.lesson_id, "animation")
            if self._tracking
            else nullcontext()
        ):
            project = self._animator.generate(
                AnimationInput(
                    guide_with_memories(
                        style.apply_to_guide(state.curriculum.guide)
                        if style
                        else state.curriculum.guide,
                        memory_notes,
                    ),
                    lesson.plan,
                    lesson.storyboard,
                    lesson.alignment,
                    tuple(audio),
                    style.visual_direction() if style else request.visual_style,
                    generation_mode=request.generation_mode,
                    animator_model=request.animator_model,
                    prepare_elements=request.prepare_elements,
                    animation_backend=request.animation_backend,
                    visual_style_id=style.visual_style_id if style else "flat-vector-science",
                    visual_style_version=style.visual_style_version if style else 1,
                    review_output=style.review_output if style else True,
                    existing_project=None
                    if request.session_id or request.message
                    else (
                        lesson.animation
                        if lesson.animation is not None
                        and lesson.animation.review_status == "pending"
                        else lesson.review_source(style)
                    ),
                    source_ready=source_ready,
                    visual_feedback=request.message,
                    previous_project_key=lesson.animation.project_key
                    if lesson.animation and (request.session_id or request.message)
                    else "",
                    regeneration_key=artifact_hash(asdict(lesson))
                    if request.session_id or request.message
                    else "",
                    session=AgentSessionContext(
                        request.owner_id or before.owner_id or "",
                        request.lesson_id,
                        request.job_id,
                        request.session_id,
                    )
                    if request.owner_id is not None or before.owner_id is not None
                    else None,
                    reviewer_session_id=request.reviewer_session_id,
                )
            )
        if project.lesson_id != request.lesson_id:
            raise AnimationUnavailable("Animator returned another lesson")
        with self._uow:
            current = self._courses.require_for_syllabus_change(course_id)
            if (
                not _same_content(current, before)
                or self._conversations.get_by_course_id(course_id) != state
            ):
                raise CourseConflict("Course changed during animation; reload and retry")
            updated = current.animate_lesson(request.lesson_id, project)
            self._courses.save(updated)
            self._uow.commit()
        return course_response(updated)


def _same_content(current: Course, before: Course) -> bool:
    current, before = without_course_images(current), without_course_images(before)
    # Learner progress can advance independently while the same lesson encodes.
    return all(
        getattr(current, field.name) == getattr(before, field.name)
        for field in fields(Course)
        if field.name not in {"reviewed", "completed", "attempts"}
    )
