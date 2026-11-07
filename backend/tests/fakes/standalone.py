from app.courses.domain.errors import CourseNotFound


class InMemoryStandaloneLessons:
    def __init__(self):
        self.items = {}

    def require_by_id(self, lesson_id):
        lesson = self.items.get(str(lesson_id))
        if lesson is None:
            raise CourseNotFound("Lesson not found")
        return lesson

    def require_for_change(self, lesson_id):
        return self.require_by_id(lesson_id)

    def list_by_owner(self, owner_id, limit, offset):
        items = [ls for ls in self.items.values() if ls.owner_id == owner_id]
        return tuple(items[offset : offset + limit])

    def add(self, lesson):
        self.items[str(lesson.content.id)] = lesson

    def save(self, lesson):
        self.items[str(lesson.content.id)] = lesson
