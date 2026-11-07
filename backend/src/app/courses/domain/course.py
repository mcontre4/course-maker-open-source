from dataclasses import dataclass, replace
from typing import Literal

from app.courses.domain.animation import AnimationProject
from app.courses.domain.duration import Duration
from app.courses.domain.errors import ContentNotReady, CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import CourseId
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.quiz import Question, QuizAttempt
from app.courses.domain.speech import LessonAlignment
from app.courses.domain.standalone import LessonOwnerId
from app.courses.domain.storyboard import Storyboard, StoryboardGeneration
from app.courses.domain.style import LessonStyle
from app.courses.domain.syllabus import Chapter, Lesson
from app.courses.domain.validation import text


@dataclass(frozen=True)
class Course:
    id: CourseId
    title: str
    description: str
    duration: Duration
    image: str = ""
    status: Literal["draft", "ready"] = "draft"
    chapters: tuple[Chapter, ...] = ()
    reviewed: tuple[str, ...] = ()
    completed: tuple[str, ...] = ()
    attempts: tuple[QuizAttempt, ...] = ()
    style: LessonStyle | None = None
    previous_styles: tuple[LessonStyle, ...] = ()
    owner_id: str | None = None

    def __post_init__(self) -> None:
        if self.owner_id is not None:
            LessonOwnerId(self.owner_id)
        text(self.title, 120)
        text(self.description, 2000)
        if self.status not in ("draft", "ready"):
            raise CourseError("Invalid course status")
        self._validate_syllabus()
        self._validate_progress()
        if self.status == "ready" and not self.chapters:
            raise CourseError("A ready course requires a syllabus")

    def _validate_syllabus(self) -> None:
        lesson_ids = [str(lesson.id) for chapter in self.chapters for lesson in chapter.lessons]
        if (
            len(self.chapters) > 50
            or len({chapter.id for chapter in self.chapters}) != len(self.chapters)
            or len(set(lesson_ids)) != len(lesson_ids)
        ):
            raise CourseError("Chapter and lesson IDs must be unique")

    def _validate_progress(self) -> None:
        lesson_ids = {str(lesson.id) for chapter in self.chapters for lesson in chapter.lessons}
        if (
            not set(self.completed) <= set(self.reviewed) <= lesson_ids
            or len(set(self.reviewed)) != len(self.reviewed)
            or len(set(self.completed)) != len(self.completed)
            or (self.status == "draft" and (self.reviewed or self.completed))
        ):
            raise CourseError("Invalid course progress")
        if (
            len(self.attempts) > 1000
            or len({a.id for a in self.attempts}) != len(self.attempts)
            or any(a.lesson_id not in self.reviewed for a in self.attempts)
        ):
            raise CourseError("Invalid quiz attempt history")

    def require_draft(self) -> None:
        if self.status != "draft":
            raise CourseConflict("Only draft courses can be edited")

    def lesson(self, lesson_id: str) -> Lesson:
        for chapter in self.chapters:
            for lesson in chapter.lessons:
                if str(lesson.id) == lesson_id:
                    return lesson
        raise CourseNotFound("Lesson not found")

    def approve(self) -> "Course":
        if not self.chapters:
            raise ContentNotReady("Add a syllabus before approving the course")
        return replace(self, status="ready")

    def _replace_lesson(self, updated: Lesson) -> "Course":
        chapters = tuple(
            replace(
                chapter,
                lessons=tuple(
                    updated if item.id == updated.id else item for item in chapter.lessons
                ),
            )
            for chapter in self.chapters
        )
        return replace(self, chapters=chapters)

    def require_style_change(self, lesson_id: str | None) -> None:
        lessons = (
            (self.lesson(lesson_id),)
            if lesson_id
            else tuple(
                item for chapter in self.chapters for item in chapter.lessons if item.style is None
            )
        )
        if any(str(item.id) in self.reviewed for item in lessons):
            raise CourseConflict("Reviewed lessons retain their approved style")
        if (lesson_id is None and len(self.previous_styles) >= 50) or any(
            len(item.previous_versions) >= 50 for item in lessons
        ):
            raise CourseConflict("Style history limit reached")

    def restyle(self, style: LessonStyle | None, lesson_id: str | None = None) -> "Course":
        self.require_style_change(lesson_id)
        lessons = (
            (self.lesson(lesson_id),)
            if lesson_id
            else tuple(
                item for chapter in self.chapters for item in chapter.lessons if item.style is None
            )
        )
        updated = self
        for item in lessons:
            updated = updated._replace_lesson(
                item.restyle(
                    style if lesson_id else None,
                    self.style if lesson_id else style,
                    previous_style=self.style,
                )
            )
        if lesson_id is None:
            updated = replace(
                updated,
                style=style,
                previous_styles=(*self.previous_styles, self.style)
                if self.style
                else self.previous_styles,
            )
        return updated

    def edit_topic(self, lesson_id: str, topic: str, operation: str) -> "Course":
        self.require_draft()
        lesson = self.lesson(lesson_id)
        text(topic, 200)
        topic = topic.strip()
        if operation == "add":
            topics = tuple(dict.fromkeys((*lesson.topics, topic)))
        elif operation == "remove":
            topics = tuple(item for item in lesson.topics if item != topic)
        else:
            raise CourseError("Unknown topic operation")
        return self._replace_lesson(replace(lesson, topics=topics))

    def plan_lesson(self, lesson_id: str, plan: LessonPlan, generation: PlanGeneration) -> "Course":
        if self.status != "ready":
            raise CourseConflict("Approve the syllabus before planning lessons")
        if lesson_id in self.reviewed:
            raise CourseConflict("A reviewed lesson cannot receive a new teaching plan")
        if plan.lesson_id != lesson_id:
            raise CourseError("A teaching plan must belong to its lesson")
        return self._replace_lesson(
            replace(
                self.lesson(lesson_id),
                interactive=None,
                plan=plan,
                plan_generation=generation,
                alignment=None,
                animation=None,
                storyboard=None,
                storyboard_generation=None,
                video_url=None,
                video_asset_id=None,
                quiz=(),
            )
        )

    def storyboard_lesson(
        self, lesson_id: str, storyboard: Storyboard, generation: StoryboardGeneration
    ) -> "Course":
        if self.status != "ready":
            raise CourseConflict("Approve the syllabus before generating storyboards")
        if lesson_id in self.reviewed:
            raise CourseConflict("A reviewed lesson cannot receive a new storyboard")
        lesson = self.lesson(lesson_id)
        if lesson.plan is None:
            raise CourseConflict("Generate the lesson plan before generating a storyboard")
        storyboard.validate_plan(lesson.plan, lesson.minutes)
        return self._replace_lesson(
            replace(
                lesson,
                alignment=None,
                animation=None,
                storyboard=storyboard,
                storyboard_generation=generation,
                video_url=None,
                video_asset_id=None,
                quiz=(),
            )
        )

    def align_lesson(self, lesson_id: str, alignment: LessonAlignment) -> "Course":
        lesson = self.lesson(lesson_id)
        if self.status != "ready" or lesson.storyboard is None or lesson_id in self.reviewed:
            raise CourseConflict("A saved, unreviewed storyboard is required for narration")
        alignment.validate_storyboard(lesson.storyboard)
        return self._replace_lesson(
            replace(
                lesson, alignment=alignment, animation=None, video_url=None, video_asset_id=None
            )
        )

    def animate_lesson(self, lesson_id: str, project: AnimationProject) -> "Course":
        lesson = self.lesson(lesson_id)
        if (
            self.status != "ready"
            or lesson.alignment is None
            or project.lesson_id != lesson_id
            or (
                lesson_id in self.reviewed
                and (lesson.animation is None or lesson.animation.review_status != "pending")
            )
            or abs(project.duration_sec - lesson.alignment.duration_sec) > 0.001
        ):
            raise CourseConflict("Animation must match an aligned, unreviewed lesson")
        return self._replace_lesson(
            replace(lesson, animation=project, video_url=None, video_asset_id=None)
        )

    def set_content(
        self,
        lesson_id: str,
        video_url: str | None,
        quiz: tuple[Question, ...],
        video_asset_id: str | None,
    ) -> "Course":
        lesson = self.lesson(lesson_id)
        if lesson_id in self.reviewed:
            raise CourseConflict("Content cannot change after the lesson has been reviewed")
        return self._replace_lesson(
            replace(lesson, video_url=video_url, quiz=quiz, video_asset_id=video_asset_id)
        )

    def review(self, lesson_id: str) -> "Course":
        lesson = self.lesson(lesson_id)
        if self.status != "ready" or not (
            lesson.video_url or lesson.video_asset_id or lesson.animation
        ):
            raise ContentNotReady("Approve the course and supply a lesson video before reviewing")
        return replace(self, reviewed=tuple(dict.fromkeys((*self.reviewed, lesson_id))))

    def submit(self, lesson_id: str, answers: tuple[int, ...], attempt_id: str) -> "Course":
        lesson = self.lesson(lesson_id)
        if self.status != "ready" or lesson_id not in self.reviewed or not lesson.quiz:
            raise ContentNotReady("Review the lesson and supply its quiz before submitting answers")
        if len(self.attempts) >= 1000:
            raise CourseConflict("Course quiz attempt limit reached")
        attempt = QuizAttempt.grade(attempt_id, lesson_id, answers, lesson.quiz)
        completed = self.completed
        if attempt.passed:
            completed = tuple(dict.fromkeys((*completed, lesson_id)))
        return replace(self, completed=completed, attempts=(*self.attempts, attempt))
