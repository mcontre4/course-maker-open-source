"""A lesson owned independently of any course."""

from dataclasses import dataclass, replace
from enum import StrEnum

from app.courses.domain.curriculum import CourseGuide, PlannedChapter, PlannedLesson
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.style import LessonStyle
from app.courses.domain.syllabus import Lesson
from app.courses.domain.validation import text
from app.shared.domain.prefixed_uuid import PrefixedUuid


class LessonOwnerId(PrefixedUuid):
    prefix = "user_"


@dataclass(frozen=True)
class LessonTurn:
    user: str
    assistant: str


class LessonFlow(StrEnum):
    GUIDED = "guided"
    AUTOMATIC = "automatic"


@dataclass(frozen=True)
class StandaloneLesson:
    owner_id: LessonOwnerId
    description: str
    content: Lesson
    revision: int = 0
    approved: bool = False
    turns: tuple[LessonTurn, ...] = ()
    flow: LessonFlow = LessonFlow.GUIDED

    def __post_init__(self) -> None:
        text(self.description, 2000)
        text(self.content.title, 120)
        if not 1 <= self.content.minutes <= 10:
            raise CourseError("Standalone lessons must be between 1 and 10 minutes")
        if (
            self.content.plan
            and self.content.plan.feasibility_status != "infeasible"
            and sum(beat.seconds for beat in self.content.plan.beats) > 600
        ):
            raise CourseError("Standalone lesson outlines must fit within 10 minutes")
        if (
            self.content.storyboard
            and sum(scene.target_duration_sec for scene in self.content.storyboard.scenes) > 600
        ):
            raise CourseError("Standalone lesson scripts must fit within 10 minutes")
        if self.content.alignment and self.content.alignment.duration_sec > 600:
            raise CourseError("Standalone lesson narration must not exceed 10 minutes")
        if self.revision < 0 or len(self.turns) > 50:
            raise CourseError("Lesson conversation limit reached")
        if self.approved and self.content.plan is None:
            raise CourseError("Approve a lesson outline before generating media")
        if self.approved and self.content.plan is not None:
            self.content.plan.require_feasible()
        if self.content.storyboard is not None and not self.approved:
            raise CourseError("Media requires an approved lesson outline")

    def require_owner(self, owner_id: str) -> None:
        if str(self.owner_id) != owner_id:
            raise CourseNotFound("Lesson not found")

    def require_revision(self, revision: int) -> None:
        if self.revision != revision:
            raise CourseConflict("Lesson changed; reload before continuing")

    def update_details(
        self,
        title: str,
        description: str,
        minutes: int,
        style: LessonStyle | None = None,
        flow: LessonFlow | None = None,
    ) -> "StandaloneLesson":
        title, description = lesson_details(title, description)
        flow = flow if flow is not None else self.flow
        style = style if style is not None else self.content.style
        if (title, description, minutes, style) == (
            self.content.title,
            self.description,
            self.content.minutes,
            self.content.style,
        ):
            return (
                self if flow == self.flow else replace(self, flow=flow, revision=self.revision + 1)
            )
        content = self.content.restyle(style) if style != self.content.style else self.content
        if (title, description, minutes) != (
            self.content.title,
            self.description,
            self.content.minutes,
        ):
            content = content.revise_outline(title, (title,), minutes, invalidate_content=True)
        return replace(
            self,
            description=description,
            flow=flow,
            content=content,
            revision=self.revision + 1,
            approved=self.approved and content.plan is not None,
        )

    def brief(self) -> PlannedLesson:
        return PlannedLesson(
            str(self.content.id),
            "standalone",
            self.content.title,
            self.content.plan.objectives
            if self.content.plan
            else (f"Understand {self.content.title}"[:200],),
            self.content.topics,
            (),
            (),
            "Adapt to the learner's description",
            self.content.minutes,
            0,
            0,
            0,
            1,
            "A complete standalone lesson with no surrounding course.",
        )

    def guide(self) -> CourseGuide:
        guide = CourseGuide(
            "Adapt to the learner's description",
            (self.content.title,),
            (),
            "Clear, concise, self-contained explanations with concrete visual examples.",
            (),
            ("Introduce concepts before applying them",),
            (
                "Keep the lesson self-contained and within the requested duration; "
                "never exceed 600 seconds",
                "Follow the latest approved plan for topics, examples, audience and scope",
            ),
        )

        return self.content.style.apply_to_guide(guide) if self.content.style else guide

    def chapter(self) -> PlannedChapter:
        return PlannedChapter("standalone", self.content.title, self.description, (self.brief(),))

    def revise(
        self, message: str, plan: LessonPlan, generation: PlanGeneration
    ) -> "StandaloneLesson":
        text(message, 2000)
        if len(self.turns) >= 50:
            raise CourseConflict("Lesson conversation limit reached")
        plan.validate_brief(
            str(self.content.id), self.brief().objectives, self.content.topics, self.content.minutes
        )
        content = self.content.revise_outline(
            self.content.title, self.content.topics, self.content.minutes, invalidate_content=True
        )
        content = replace(content, plan=plan, plan_generation=generation)
        summary = "\n".join(f"{beat.title}: {beat.teaching_notes}" for beat in plan.beats)
        return replace(
            self,
            content=content,
            revision=self.revision + 1,
            approved=False,
            turns=(*self.turns, LessonTurn(message, summary)),
        )

    def edit_outline(self, plan: LessonPlan) -> "StandaloneLesson":
        if self.content.plan is None:
            raise CourseConflict("Generate a lesson outline before editing it")
        for objective in plan.objectives:
            text(objective, 200)
        plan.validate_brief(
            str(self.content.id), plan.objectives, self.content.topics, self.content.minutes
        )
        if plan == self.content.plan:
            return self
        content = self.content.revise_outline(
            self.content.title, self.content.topics, self.content.minutes, invalidate_content=True
        )
        return replace(
            self,
            content=replace(content, plan=plan),
            revision=self.revision + 1,
            approved=False,
        )

    def approve(self) -> "StandaloneLesson":
        if self.content.plan is None:
            raise CourseConflict("Generate a lesson outline before approving it")
        return replace(self, approved=True, revision=self.revision + 1)

    def apply_guide_plan(
        self, plan: LessonPlan, generation: PlanGeneration | None = None
    ) -> "StandaloneLesson":
        """Chat history lives separately; applying an outline has no turn limit."""
        plan.validate_brief(
            str(self.content.id), plan.objectives, self.content.topics, self.content.minutes
        )
        content = self.content.revise_outline(
            self.content.title, self.content.topics, self.content.minutes, invalidate_content=True
        )
        return replace(
            self,
            content=replace(content, plan=plan, plan_generation=generation),
            revision=self.revision + 1,
            approved=False,
        )

    def save_media(self, content: Lesson) -> "StandaloneLesson":
        if not self.approved or content.id != self.content.id or content.plan != self.content.plan:
            raise CourseConflict("Media must match the approved lesson outline")
        if content != self.content:
            content = replace(
                content, previous_versions=self.content.preserve_playback().previous_versions
            )
        return replace(self, content=content, revision=self.revision + 1)

    def edit_script(self, narrations: tuple[str, ...]) -> "StandaloneLesson":
        storyboard = self.content.storyboard
        if storyboard is None:
            raise CourseConflict("Generate the script before editing it")
        if len(narrations) != len(storyboard.scenes):
            raise CourseError("Keep one narration for each scene in the saved script")
        if all(
            narration.strip() == scene.narration_text.strip()
            for scene, narration in zip(storyboard.scenes, narrations, strict=True)
        ):
            return self
        updated = replace(
            storyboard,
            scenes=tuple(
                scene.with_narration(narration)
                for scene, narration in zip(storyboard.scenes, narrations, strict=True)
            ),
        )
        if updated == storyboard:
            return self
        return self.save_media(
            replace(
                self.content,
                storyboard=updated,
                storyboard_generation=None,
                alignment=None,
                animation=None,
                video_url=None,
                video_asset_id=None,
            )
        )


def lesson_details(title: str, description: str) -> tuple[str, str]:
    """Infer missing lesson context without a provider call."""
    title, description = title.strip(), description.strip()
    if not title and not description:
        raise CourseError("Add a lesson title or describe what you want to learn")
    if not title:
        title = description.splitlines()[0][:120].strip()
    description = description or title
    text(title, 120)
    text(description, 2000)
    return title, description
