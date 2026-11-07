"""Apply a planned syllabus without retaining media for changed teaching content."""

from dataclasses import replace

from app.courses.domain.course import Course
from app.courses.domain.curriculum import Curriculum, PlannedLesson
from app.courses.domain.identifiers import ChapterId, LessonId
from app.courses.domain.syllabus import Chapter, Lesson


def _teaching_changed(before: PlannedLesson, after: PlannedLesson) -> bool:
    return (
        before.objectives,
        before.concepts,
        before.prerequisites,
        before.examples,
        before.level,
    ) != (after.objectives, after.concepts, after.prerequisites, after.examples, after.level)


def revise_curriculum(course: Course, plan: Curriculum, previous: Curriculum | None) -> Course:
    course.require_draft()
    chapters = {str(ch.id): ch for ch in course.chapters}
    lessons = {str(ls.id): ls for ch in course.chapters for ls in ch.lessons}
    briefs = {ls.lesson_id: ls for ch in previous.chapters for ls in ch.lessons} if previous else {}
    guide_changed = previous is not None and previous.guide != plan.guide

    def revise(brief: PlannedLesson) -> Lesson:
        existing = lessons.get(brief.lesson_id)
        if existing is None:
            return Lesson(
                LessonId(brief.lesson_id), brief.title, brief.concepts, brief.video_minutes
            )
        changed = guide_changed or (
            brief.lesson_id in briefs and _teaching_changed(briefs[brief.lesson_id], brief)
        )
        return existing.revise_outline(
            brief.title, brief.concepts, brief.video_minutes, invalidate_content=changed
        )

    return replace(
        course,
        title=plan.title,
        chapters=tuple(
            Chapter(
                ChapterId(ch.chapter_id),
                ch.title,
                ch.summary,
                tuple(revise(brief) for brief in ch.lessons),
                chapters[ch.chapter_id].image if ch.chapter_id in chapters else "",
            )
            for ch in plan.chapters
        ),
    )
