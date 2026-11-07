from dataclasses import dataclass, replace
from typing import Self

from app.courses.domain.animation import AnimationProject
from app.courses.domain.errors import CourseError
from app.courses.domain.identifiers import AssetId, ChapterId, LessonId
from app.courses.domain.interactive import LessonInteractive
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.quiz import Question
from app.courses.domain.speech import LessonAlignment
from app.courses.domain.storyboard import Storyboard, StoryboardGeneration
from app.courses.domain.style import LessonStyle
from app.courses.domain.validation import text


@dataclass(frozen=True)
class Lesson:
    id: LessonId
    title: str
    topics: tuple[str, ...]
    minutes: int
    image: str = ""
    video_url: str | None = None
    quiz: tuple[Question, ...] = ()
    video_asset_id: str | None = None
    plan: LessonPlan | None = None
    plan_generation: PlanGeneration | None = None
    storyboard: Storyboard | None = None
    storyboard_generation: StoryboardGeneration | None = None
    alignment: LessonAlignment | None = None
    animation: AnimationProject | None = None
    style: LessonStyle | None = None
    previous_versions: tuple["Lesson", ...] = ()
    interactive: LessonInteractive | None = None

    @property
    def is_published(self) -> bool:
        return bool(
            self.video_url
            or self.video_asset_id
            or (self.animation is not None and self.animation.review_status != "pending")
        )

    def __post_init__(self) -> None:
        text(self.title, 200)
        if self.interactive is not None:
            if self.plan is None:
                raise CourseError("An interactive requires its lesson plan")
            self.interactive.validate_plan(self.plan)
        if self.plan is not None:
            self.plan.validate_brief(str(self.id), self.plan.objectives, self.topics, self.minutes)
        if self.storyboard is not None:
            if self.plan is None:
                raise CourseError("A storyboard requires its lesson plan")
            self.storyboard.validate_plan(self.plan, self.minutes)
        if self.alignment is not None:
            if self.storyboard is None:
                raise CourseError("Audio alignment requires its storyboard")
            self.alignment.validate_storyboard(self.storyboard)
        if self.animation is not None:
            if (
                self.alignment is None
                or self.animation.lesson_id != str(self.id)
                or abs(self.animation.duration_sec - self.alignment.duration_sec) > 0.001
            ):
                raise CourseError("Animation requires its complete aligned lesson")
        if self.video_url and self.video_asset_id:
            raise CourseError("Choose a video URL or an uploaded asset, not both")
        if self.video_asset_id is not None:
            AssetId(self.video_asset_id)
        if (
            type(self.minutes) is not int
            or not 1 <= self.minutes <= 1440
            or not 1 <= len(self.topics) <= 50
        ):
            raise CourseError("A lesson needs a positive duration and 1–50 topics")
        for topic in self.topics:
            text(topic, 200)
        if len({q.id for q in self.quiz}) != len(self.quiz) or len(self.quiz) > 50:
            raise CourseError("Quiz question IDs must be unique; maximum 50 questions")

    def copy(
        self,
        identifier: LessonId,
        *,
        include_history: bool = True,
        title: str | None = None,
    ) -> "Lesson":
        """Rebind immutable content to an independent lesson identity.

        Without a chosen title the copy is named after its source.
        """
        from app.courses.domain.interactive import lesson_plan_hash

        chosen = title.strip() if title is not None else None
        copy_title = chosen if chosen is not None else self.title[:115].rstrip() + "-copy"
        text(copy_title, 120)
        plan = replace(self.plan, lesson_id=str(identifier)) if self.plan else None
        return replace(
            self,
            id=identifier,
            title=copy_title,
            plan=plan,
            storyboard=replace(self.storyboard, lesson_id=str(identifier))
            if self.storyboard
            else None,
            alignment=replace(self.alignment, lesson_id=str(identifier))
            if self.alignment
            else None,
            animation=replace(
                self.animation,
                lesson_id=str(identifier),
                session_id=None,
                reviewer_session_id=None,
                owner_id=None,
                job_id=None,
            )
            if self.animation
            else None,
            plan_generation=replace(self.plan_generation, session_id=None)
            if self.plan_generation
            else None,
            storyboard_generation=replace(
                self.storyboard_generation,
                usage=replace(self.storyboard_generation.usage, session_id=None),
                script_session_id=None,
            )
            if self.storyboard_generation
            else None,
            interactive=replace(self.interactive, plan_hash=lesson_plan_hash(plan))
            if self.interactive and plan
            else None,
            previous_versions=tuple(
                version.copy(identifier, include_history=False, title=chosen)
                for version in self.previous_versions
            )
            if include_history
            else (),
        )

    def review_source(self, effective_style: LessonStyle | None) -> AnimationProject | None:
        if effective_style is None or self.alignment is None:
            return None
        for previous in reversed(self.previous_versions):
            if (
                previous.style is not None
                and effective_style.change_scope(previous.style) in ("none", "review")
                and previous.plan == self.plan
                and previous.storyboard == self.storyboard
                and previous.alignment == self.alignment
                and previous.animation is not None
                and previous.animation.project_key.endswith("/javascript")
            ):
                return previous.animation
        return None

    def preserve_playback(self) -> Self:
        """Retain the completed video before a draft invalidates its media."""
        if not self.is_published:
            return self
        previous = replace(self, previous_versions=())
        if self.previous_versions and self.previous_versions[-1] == previous:
            return self
        return replace(self, previous_versions=(*self.previous_versions[-49:], previous))

    def playback_version(self, source_hash: str | None = None) -> "Lesson | None":
        versions = (self, *reversed(self.previous_versions))
        if source_hash is not None:
            return next(
                (v for v in versions if v.animation and v.animation.output_hash == source_hash),
                None,
            )
        return next((v for v in versions if v.is_published), self if self.animation else None)

    def restyle(
        self,
        style: LessonStyle | None,
        inherited: LessonStyle | None = None,
        previous_style: LessonStyle | None = None,
    ) -> "Lesson":
        effective = style or inherited or LessonStyle()
        scope = effective.change_scope(self.style or previous_style)
        if len(self.previous_versions) >= 50:
            raise CourseError("Lesson style history limit reached")
        previous = replace(self, style=self.style or previous_style, previous_versions=())
        return replace(
            self,
            style=style,
            previous_versions=(*self.previous_versions, previous),
            interactive=None if scope == "content" else self.interactive,
            plan=None if scope == "content" else self.plan,
            plan_generation=None if scope == "content" else self.plan_generation,
            storyboard=None if scope in ("content", "visuals") else self.storyboard,
            storyboard_generation=None
            if scope in ("content", "visuals")
            else self.storyboard_generation,
            alignment=None if scope not in ("none", "review") else self.alignment,
            animation=None if scope != "none" else self.animation,
            video_url=None if scope != "none" else self.video_url,
            video_asset_id=None if scope != "none" else self.video_asset_id,
            quiz=() if scope == "content" else self.quiz,
        )

    def revise_outline(
        self, title: str, topics: tuple[str, ...], minutes: int, *, invalidate_content: bool = False
    ) -> Self:
        changed = invalidate_content or (title, topics, minutes) != (
            self.title,
            self.topics,
            self.minutes,
        )
        if changed:
            self = self.preserve_playback()
        return replace(
            self,
            title=title,
            topics=topics,
            minutes=minutes,
            video_url=None if changed else self.video_url,
            video_asset_id=None if changed else self.video_asset_id,
            quiz=() if changed else self.quiz,
            interactive=None if changed else self.interactive,
            plan=None if changed else self.plan,
            plan_generation=None if changed else self.plan_generation,
            alignment=None if changed else self.alignment,
            animation=None if changed else self.animation,
            storyboard=None if changed else self.storyboard,
            storyboard_generation=None if changed else self.storyboard_generation,
        )


@dataclass(frozen=True)
class Chapter:
    id: ChapterId
    title: str
    summary: str
    lessons: tuple[Lesson, ...]
    image: str = ""

    def __post_init__(self) -> None:
        text(self.title, 200)
        if not 1 <= len(self.lessons) <= 100 or len(self.summary) > 2000:
            raise CourseError("A chapter needs 1–100 lessons and a summary up to 2000 characters")
