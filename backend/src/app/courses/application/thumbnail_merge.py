"""Allow illustration updates to coexist with teaching-content generation."""

from dataclasses import replace

from app.courses.domain.course import Course
from app.courses.domain.standalone import StandaloneLesson


def without_course_images(course: Course) -> Course:
    return replace(
        course,
        image="",
        chapters=tuple(
            replace(chapter, lessons=tuple(replace(lesson, image="") for lesson in chapter.lessons))
            for chapter in course.chapters
        ),
    )


def with_course_images(updated: Course, current: Course) -> Course:
    images = {lesson.id: lesson.image for chapter in current.chapters for lesson in chapter.lessons}
    return replace(
        updated,
        image=current.image,
        chapters=tuple(
            replace(
                chapter,
                lessons=tuple(
                    replace(lesson, image=images.get(lesson.id, lesson.image))
                    for lesson in chapter.lessons
                ),
            )
            for chapter in updated.chapters
        ),
    )


def without_lesson_image(lesson: StandaloneLesson) -> StandaloneLesson:
    return replace(lesson, content=replace(lesson.content, image=""))
