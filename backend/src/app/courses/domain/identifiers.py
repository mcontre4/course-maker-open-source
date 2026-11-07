from app.shared.domain.prefixed_uuid import PrefixedUuid


class CourseId(PrefixedUuid):
    prefix = "course_"


class ChapterId(PrefixedUuid):
    prefix = "chapter_"


class LessonId(PrefixedUuid):
    prefix = "lesson_"


class AssetId(PrefixedUuid):
    prefix = "asset_"
