from app.courses.domain.content_search import matches_search, search_rank
from app.courses.domain.errors import CourseNotFound


class InMemoryCreators:
    def __init__(self):
        self.items = {}
        self.courses = []
        self.lessons = []

    def get_by_id(self, creator_id):
        return self.items.get(str(creator_id))

    def add(self, profile):
        self.items.setdefault(str(profile.id), profile)

    def save(self, profile):
        self.items[str(profile.id)] = profile

    def courses_by_creator(self, creator_id):
        return tuple(c for c in self.courses if c.owner_id == str(creator_id))

    def lessons_by_creator(self, creator_id):
        return tuple(ls for ls in self.lessons if ls.owner_id == creator_id)

    def get_lesson(self, lesson_id):
        return next((ls for ls in self.lessons if ls.content.id == lesson_id), None)

    def require_by_id(self, course_id):
        course = next((c for c in self.courses if c.id == course_id), None)
        if course is None:
            raise CourseNotFound("Course not found")
        return course

    def latest_courses(self, limit, query=""):
        courses = [
            c
            for c in reversed(self.courses)
            if any(ls.is_published for ch in c.chapters for ls in ch.lessons)
            and (
                matches_search(query, c.title, c.description)
                or any(
                    ls.is_published and matches_search(query, ls.title)
                    for ch in c.chapters
                    for ls in ch.lessons
                )
            )
        ]
        return tuple(
            sorted(
                courses,
                key=lambda c: min(
                    search_rank(query, c.title),
                    *(
                        search_rank(query, ls.title)
                        for ch in c.chapters
                        for ls in ch.lessons
                        if ls.is_published
                    ),
                ),
            )
        )[:limit]

    def latest_lessons(self, limit, query=""):
        lessons = [
            ls
            for ls in reversed(self.lessons)
            if ls.content.is_published and matches_search(query, ls.content.title)
        ]
        return tuple(sorted(lessons, key=lambda ls: search_rank(query, ls.content.title)))[:limit]
