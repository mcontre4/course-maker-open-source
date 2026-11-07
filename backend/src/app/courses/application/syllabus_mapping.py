from app.courses.application.dto import ChapterRequest, LessonRequest, QuestionRequest
from app.courses.domain.identifiers import ChapterId, LessonId
from app.courses.domain.quiz import Question
from app.courses.domain.syllabus import Chapter, Lesson
from app.shared.domain.id_generator import IdGenerator


def new_question(request: QuestionRequest, ids: IdGenerator) -> Question:
    return Question(
        f"question_{ids.new_uuid()}",
        request.prompt,
        request.options,
        request.answer,
        request.explanation,
    )


def new_lesson(request: LessonRequest, ids: IdGenerator) -> Lesson:
    return Lesson(
        LessonId(f"lesson_{ids.new_uuid()}"),
        request.title,
        request.topics,
        request.minutes,
        request.image,
        request.video_url,
        tuple(new_question(question, ids) for question in request.quiz),
        request.video_asset_id,
    )


def new_chapter(request: ChapterRequest, ids: IdGenerator) -> Chapter:
    return Chapter(
        ChapterId(f"chapter_{ids.new_uuid()}"),
        request.title,
        request.summary,
        tuple(new_lesson(lesson, ids) for lesson in request.lessons),
        request.image,
    )
