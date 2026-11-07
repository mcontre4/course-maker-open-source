import hashlib
from contextlib import nullcontext
from dataclasses import asdict, replace

from app.courses.application.generate_storyboard import artifact_hash
from app.courses.application.guide_memory import guide_with_memories, load_memory_guidance
from app.courses.application.lesson_speech import generate_lesson_speech
from app.courses.application.standalone import _StandaloneUseCase
from app.courses.application.standalone_dto import (
    ReviseStandaloneLessonRequest,
    StandaloneLessonResponse,
    standalone_response,
)
from app.courses.domain.animation import AnimationProject
from app.courses.domain.errors import CourseConflict
from app.courses.domain.speech import SpeechSettings
from app.courses.domain.storyboard import StoryboardGeneration
from app.courses.ports.agent_sessions import AgentSessionContext
from app.courses.ports.animator import AnimationInput, AnimationUnavailable, Animator
from app.courses.ports.guide import GuideRepository
from app.courses.ports.lesson_quiz import QuizJob, QuizJobs
from app.courses.ports.speech import SpeechArtifacts, SpeechSynthesizer
from app.courses.ports.spend import UsageTracking
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.courses.ports.storyboard_agent import (
    STORYBOARD_PROMPT_VERSION,
    StoryboardAgent,
    StoryboardAgentRequest,
)
from app.shared.application.unit_of_work import UnitOfWork

VISUAL_STYLE = (
    "Clear educational diagrams, warm neutral background, readable labels and restrained motion."
)


class GenerateStandaloneStoryboard(_StandaloneUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        agent: StoryboardAgent,
        tracking: UsageTracking | None = None,
        memories: GuideRepository | None = None,
        quiz_jobs: QuizJobs | None = None,
    ) -> None:
        super().__init__(lessons, uow)
        self._memories = memories
        self._tracking = tracking
        self._agent = agent
        self._quiz_jobs = quiz_jobs

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id)
            before.require_revision(request.expected_revision)
            memory_notes = load_memory_guidance(self._memories, request.owner_id, request.lesson_id)
            if not before.approved or before.content.plan is None:
                raise CourseConflict("Approve the lesson outline before generating the video")
        if self._quiz_jobs:
            self._quiz_jobs.enqueue(
                QuizJob(request.lesson_id, request.owner_id, request.generation_mode)
            )
        if (
            before.content.storyboard is not None
            and request.regenerate_from != "script"
            and not (request.session_id or request.script_session_id or request.message)
        ):
            return standalone_response(before)
        inputs = StoryboardAgentRequest(
            before.content.plan,
            guide_with_memories(before.guide(), memory_notes),
            before.content.minutes,
            before.content.style.visual_direction() if before.content.style else VISUAL_STYLE,
            generation_mode=request.generation_mode,
            visual_style_id=(
                before.content.style.visual_style_id
                if before.content.style
                else "flat-vector-science"
            ),
            visual_style_version=(
                before.content.style.visual_style_version if before.content.style else 1
            ),
            session=AgentSessionContext(
                request.owner_id, request.lesson_id, request.job_id, request.session_id
            ),
            script_session_id=request.script_session_id,
            message=request.message,
        )
        with (
            self._tracking.scope(None, request.lesson_id, "storyboard")
            if self._tracking
            else nullcontext()
        ):
            result = self._agent.run(inputs)
        result.storyboard.validate_plan(before.content.plan, before.content.minutes)
        generation = StoryboardGeneration(
            result.usage,
            artifact_hash({"request": asdict(inputs), "prompt_version": STORYBOARD_PROMPT_VERSION}),
            artifact_hash(asdict(result.storyboard)),
            STORYBOARD_PROMPT_VERSION,
            before.content.style.visual_direction() if before.content.style else VISUAL_STYLE,
            script_session_id=result.script_session_id,
        )
        return self._save(
            before,
            before.save_media(
                replace(
                    before.content,
                    storyboard=result.storyboard,
                    storyboard_generation=generation,
                    alignment=None,
                    animation=None,
                    video_url=None,
                    video_asset_id=None,
                )
            ),
        )


class GenerateStandaloneSpeech(_StandaloneUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        synthesizer: SpeechSynthesizer,
        artifacts: SpeechArtifacts,
        settings: SpeechSettings,
        gap: float = 0.0,
        tracking: UsageTracking | None = None,
    ) -> None:
        super().__init__(lessons, uow)
        self._tracking = tracking
        self._synthesizer, self._artifacts, self._settings, self._gap = (
            synthesizer,
            artifacts,
            settings,
            gap,
        )

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id)
            before.require_revision(request.expected_revision)
            if not before.approved or before.content.storyboard is None:
                raise CourseConflict("Generate the storyboard before narration")
            style = before.content.style
            settings = (
                replace(
                    self._settings,
                    voice_id=style.voice_id or self._settings.voice_id,
                    delivery=style.speech_delivery(),
                )
                if style
                else self._settings
            )
            cached = before.content.alignment
            if cached and (
                cached.settings != settings or cached.silence_between_scenes_sec != self._gap
            ):
                cached = None
        regenerate = request.regenerate_from in ("script", "speech")
        speech_content = (
            replace(
                before.content, alignment=None, animation=None, video_url=None, video_asset_id=None
            )
            if regenerate or cached is None
            else before.content
        )
        prefix = f"lessons/{before.content.id}/speech"
        if regenerate:
            prefix += f"/regenerations/{before.revision}"
        with (
            self._tracking.scope(None, request.lesson_id, "speech")
            if self._tracking
            else nullcontext()
        ):
            alignment = generate_lesson_speech(
                speech_content,
                self._synthesizer,
                self._artifacts,
                settings,
                self._gap,
                prefix,
            )
        if alignment == cached:
            return standalone_response(before)
        return self._save(
            before,
            before.save_media(
                replace(
                    before.content,
                    alignment=alignment,
                    animation=None,
                    video_url=None,
                    video_asset_id=None,
                )
            ),
        )


class GenerateStandaloneAnimation(_StandaloneUseCase):
    def __init__(
        self,
        lessons: StandaloneLessons,
        uow: UnitOfWork,
        animator: Animator,
        artifacts: SpeechArtifacts,
        tracking: UsageTracking | None = None,
        memories: GuideRepository | None = None,
    ) -> None:
        super().__init__(lessons, uow)
        self._memories = memories
        self._tracking = tracking
        self._animator, self._artifacts = animator, artifacts

    def execute(self, request: ReviseStandaloneLessonRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id)
            before.require_revision(request.expected_revision)
            memory_notes = load_memory_guidance(self._memories, request.owner_id, request.lesson_id)
            content = before.content
            if (
                not before.approved
                or content.plan is None
                or content.storyboard is None
                or content.alignment is None
            ):
                raise CourseConflict("Approved outline, storyboard and narration are required")
        if (
            request.regenerate_from is None
            and request.session_id is None
            and not request.message
            and request.reviewer_session_id is None
            and content.animation is not None
            and content.animation.review_status != "pending"
            and content.animation.backend == request.animation_backend.value
            and content.animation.prepare_elements == request.prepare_elements
            and (
                request.animator_model is None
                or content.animation.model == request.animator_model.value
            )
        ):
            self._animator.verify(content.animation)
            return standalone_response(before)
        if content.alignment.storyboard_hash != artifact_hash(asdict(content.storyboard)):
            raise CourseConflict("Storyboard changed after narration")
        audio = []
        for scene in content.alignment.scenes:
            data = self._artifacts.read(scene.audio_key)
            if data is None or hashlib.sha256(data).hexdigest() != scene.audio_sha256:
                raise AnimationUnavailable("Aligned audio is missing or corrupt")
            audio.append(data)

        def source_ready(project: AnimationProject) -> None:
            nonlocal before
            if project.lesson_id != request.lesson_id:
                raise AnimationUnavailable("Animator returned another lesson")
            updated = before.save_media(
                replace(before.content, animation=project, video_url=None, video_asset_id=None)
            )
            self._save(before, updated)
            before = updated

        with (
            self._tracking.scope(None, request.lesson_id, "animation")
            if self._tracking
            else nullcontext()
        ):
            project = self._animator.generate(
                AnimationInput(
                    guide_with_memories(before.guide(), memory_notes),
                    content.plan,
                    content.storyboard,
                    content.alignment,
                    tuple(audio),
                    before.content.style.visual_direction()
                    if before.content.style
                    else VISUAL_STYLE,
                    generation_mode=request.generation_mode,
                    animator_model=request.animator_model,
                    prepare_elements=request.prepare_elements,
                    animation_backend=request.animation_backend,
                    visual_style_id=content.style.visual_style_id
                    if content.style
                    else "flat-vector-science",
                    visual_style_version=content.style.visual_style_version if content.style else 1,
                    review_output=content.style.review_output if content.style else True,
                    existing_project=None
                    if request.regenerate_from is not None or request.session_id or request.message
                    else (
                        content.animation
                        if content.animation is not None
                        and content.animation.review_status == "pending"
                        else content.review_source(content.style)
                    ),
                    regeneration_key=str(before.revision)
                    if request.regenerate_from or request.session_id or request.message
                    else "",
                    visual_feedback=request.message,
                    previous_project_key=content.animation.project_key
                    if content.animation and (request.session_id or request.message)
                    else "",
                    source_ready=source_ready,
                    session=AgentSessionContext(
                        request.owner_id, request.lesson_id, request.job_id, request.session_id
                    ),
                    reviewer_session_id=request.reviewer_session_id,
                )
            )
        return self._save(
            before,
            before.save_media(
                replace(content, animation=project, video_url=None, video_asset_id=None)
            ),
        )
