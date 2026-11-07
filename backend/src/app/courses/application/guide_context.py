import json
from dataclasses import asdict, dataclass, replace

from app.courses.application.guide_dto import GuideThreadResponse, GuideTurnResponse
from app.courses.application.thumbnail_merge import (
    with_course_images,
    without_course_images,
    without_lesson_image,
)
from app.courses.domain.course import Course
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.guide import GuideThread, GuideThreadId, GuideTurn
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.standalone import StandaloneLesson
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.guide import GuideAgent, GuideOutlineCodec, GuideRepository
from app.courses.ports.lesson_agent import LessonAgent
from app.courses.ports.spend import UsageTracking
from app.courses.ports.standalone_lessons import StandaloneLessons
from app.courses.ports.syllabus_agent import (
    SyllabusAgent,
    SyllabusConversation,
    SyllabusConversations,
)
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class GuideDependencies:
    repository: GuideRepository
    lessons: StandaloneLessons
    courses: CourseRepository
    syllabuses: SyllabusConversations
    uow: UnitOfWork
    ids: IdGenerator
    agent: GuideAgent
    lesson_agent: LessonAgent
    syllabus_agent: SyllabusAgent
    codec: GuideOutlineCodec
    tracking: UsageTracking | None = None


@dataclass(frozen=True)
class GuideResource:
    lesson: StandaloneLesson | None = None
    course: Course | None = None
    syllabus: SyllabusConversation | None = None

    def _without_thumbnails(self) -> "GuideResource":
        return replace(
            self,
            lesson=without_lesson_image(self.lesson) if self.lesson else None,
            course=without_course_images(self.course) if self.course else None,
        )

    def _with_thumbnails(self, current: "GuideResource") -> "GuideResource":
        return replace(
            self,
            lesson=replace(
                self.lesson,
                content=replace(
                    self.lesson.content,
                    image=current.lesson.content.image,
                ),
            )
            if self.lesson and current.lesson
            else self.lesson,
            course=with_course_images(self.course, current.course)
            if self.course and current.course
            else self.course,
        )

    def _context_json(self) -> str:
        if self.lesson:
            ls = self.lesson
            return json.dumps(
                {
                    "title": ls.content.title,
                    "description": ls.description,
                    "minutes": ls.content.minutes,
                    "revision": ls.revision,
                    "approved": ls.approved,
                    "outline": asdict(ls.content.plan) if ls.content.plan else None,
                    "style": asdict(ls.content.style) if ls.content.style else None,
                    "has_script": ls.content.storyboard is not None,
                    "has_animation": ls.content.animation is not None,
                }
            )
        assert self.course is not None
        course = self.course
        curriculum = self.syllabus.curriculum if self.syllabus else None
        return json.dumps(
            {
                "course": {
                    "id": str(course.id),
                    "title": course.title,
                    "description": course.description,
                    "duration": asdict(course.duration),
                    "status": course.status,
                    "style": asdict(course.style) if course.style else None,
                    "chapters": [
                        {
                            "id": str(ch.id),
                            "title": ch.title,
                            "summary": ch.summary,
                            "lessons": [
                                {
                                    "id": str(ls.id),
                                    "title": ls.title,
                                    "topics": ls.topics,
                                    "minutes": ls.minutes,
                                    "has_outline": ls.plan is not None,
                                    "has_script": ls.storyboard is not None,
                                    "has_animation": ls.animation is not None,
                                }
                                for ls in ch.lessons
                            ],
                        }
                        for ch in course.chapters
                    ],
                },
                "teaching_context": {
                    "audience": curriculum.audience,
                    "outcomes": curriculum.outcomes,
                    "guide": asdict(curriculum.guide),
                    "assumptions": curriculum.assumptions,
                    "warnings": curriculum.warnings,
                }
                if curriculum
                else None,
            },
        )


def thread_response(
    thread: GuideThread, turns: tuple[GuideTurn, ...] = (), has_more: bool = False
) -> GuideThreadResponse:
    return GuideThreadResponse(
        str(thread.id),
        thread.resource_id,
        thread.guide,
        thread.title,
        thread.revision,
        tuple(GuideTurnResponse(str(t.id), t.revision, t.user, t.assistant) for t in turns),
        has_more,
    )


class _GuideUseCase:
    def __init__(self, dependencies: GuideDependencies) -> None:
        self._d = dependencies

    def _resource(self, resource_id: str, owner_id: str, *, lock: bool = False) -> GuideResource:
        if resource_id.startswith("lesson_"):
            lesson = (
                self._d.lessons.require_for_change(LessonId(resource_id))
                if lock
                else self._d.lessons.require_by_id(LessonId(resource_id))
            )
            lesson.require_owner(owner_id)
            return GuideResource(lesson=lesson)
        if resource_id.startswith("course_"):
            course = (
                self._d.courses.require_for_syllabus_change(CourseId(resource_id))
                if lock
                else self._d.courses.require_by_id(CourseId(resource_id))
            )
            if course.owner_id != owner_id:
                raise CourseNotFound("Course not found")
            state = self._d.syllabuses.get_by_course_id(CourseId(resource_id))
            return GuideResource(course=course, syllabus=state or SyllabusConversation(resource_id))
        raise CourseNotFound("Lesson or course not found")

    def _thread(self, thread_id: str, owner_id: str) -> GuideThread:
        thread = self._d.repository.require_by_id(GuideThreadId(thread_id))
        if thread.owner_id != owner_id:
            raise CourseNotFound("Chat not found")
        self._resource(thread.resource_id, owner_id)
        return thread
