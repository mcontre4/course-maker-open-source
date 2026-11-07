from dataclasses import asdict
from typing import Any

from pydantic import TypeAdapter

from app.courses.domain.animation import AnimationProject
from app.courses.domain.course import Course
from app.courses.domain.duration import Duration
from app.courses.domain.identifiers import ChapterId, CourseId, LessonId
from app.courses.domain.interactive import LessonInteractive
from app.courses.domain.lesson_plan import LessonPlan, PlanGeneration
from app.courses.domain.quiz import Question, QuizAttempt
from app.courses.domain.speech import LessonAlignment
from app.courses.domain.storyboard import Storyboard, StoryboardGeneration
from app.courses.domain.style import LessonStyle
from app.courses.domain.syllabus import Chapter, Lesson


def encode(course: Course) -> dict[str, Any]:
    data = asdict(course)
    data["id"] = str(course.id)
    for chapter, source in zip(data["chapters"], course.chapters, strict=True):
        chapter["id"] = str(source.id)
        for lesson, original in zip(chapter["lessons"], source.lessons, strict=True):
            lesson.update(encode_lesson(original))
    return data


def encode_lesson(lesson: Lesson) -> dict[str, Any]:
    data = asdict(lesson)
    data["id"] = str(lesson.id)
    data["previous_versions"] = [encode_lesson(v) for v in lesson.previous_versions]
    return data


def _question(data: dict[str, Any]) -> Question:
    return Question(
        data["id"], data["prompt"], tuple(data["options"]), data["answer"], data["explanation"]
    )


def _lesson(data: dict[str, Any]) -> Lesson:
    return Lesson(
        interactive=TypeAdapter(LessonInteractive).validate_python(data["interactive"])
        if data.get("interactive")
        else None,
        style=TypeAdapter(LessonStyle).validate_python(data["style"])
        if data.get("style")
        else None,
        previous_versions=tuple(_lesson(v) for v in data.get("previous_versions", [])),
        id=LessonId(data["id"]),
        title=data["title"],
        topics=tuple(data["topics"]),
        minutes=data["minutes"],
        image=data["image"],
        video_url=data["video_url"],
        video_asset_id=data.get("video_asset_id"),
        quiz=tuple(_question(question) for question in data["quiz"]),
        animation=TypeAdapter(AnimationProject).validate_python(data["animation"])
        if data.get("animation")
        else None,
        alignment=TypeAdapter(LessonAlignment).validate_python(data["alignment"])
        if data.get("alignment")
        else None,
        plan_generation=PlanGeneration(**data["plan_generation"])
        if data.get("plan_generation")
        else None,
        storyboard=TypeAdapter(Storyboard).validate_python(data["storyboard"])
        if data.get("storyboard")
        else None,
        storyboard_generation=TypeAdapter(StoryboardGeneration).validate_python(
            data["storyboard_generation"]
        )
        if data.get("storyboard_generation")
        else None,
        plan=TypeAdapter(LessonPlan).validate_python(data["plan"]) if data.get("plan") else None,
    )


def _chapter(data: dict[str, Any]) -> Chapter:
    return Chapter(
        ChapterId(data["id"]),
        data["title"],
        data["summary"],
        tuple(_lesson(lesson) for lesson in data["lessons"]),
        data["image"],
    )


def _attempt(data: dict[str, Any]) -> QuizAttempt:
    return QuizAttempt(
        data["id"],
        data["lesson_id"],
        tuple(data["answers"]),
        data["score"],
        data["total"],
        data["passed"],
    )


def decode(data: dict[str, Any]) -> Course:
    return Course(
        style=TypeAdapter(LessonStyle).validate_python(data["style"])
        if data.get("style")
        else None,
        previous_styles=tuple(
            TypeAdapter(LessonStyle).validate_python(v) for v in data.get("previous_styles", [])
        ),
        owner_id=data.get("owner_id"),
        id=CourseId(data["id"]),
        title=data["title"],
        description=data["description"],
        duration=Duration(**data["duration"]),
        image=data["image"],
        status=data["status"],
        chapters=tuple(_chapter(chapter) for chapter in data["chapters"]),
        reviewed=tuple(data["reviewed"]),
        completed=tuple(data["completed"]),
        attempts=tuple(_attempt(attempt) for attempt in data["attempts"]),
    )
