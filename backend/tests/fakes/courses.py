from uuid import UUID

from app.courses.domain.errors import CourseNotFound


class SequenceIds:
    def __init__(self):
        self.count = 0

    def new_uuid(self):
        self.count += 1
        return UUID(int=self.count)


class InMemoryCourses:
    def __init__(self):
        self.items = {}

    def get_by_id(self, course_id):
        return self.items.get(str(course_id))

    def require_by_id(self, course_id):
        result = self.get_by_id(course_id)
        if result is None:
            raise CourseNotFound("Course not found")
        return result

    def require_for_syllabus_change(self, course_id):
        return self.require_by_id(course_id)

    def _matching(self, search, status):
        return sorted(
            (
                c
                for c in self.items.values()
                if search.lower() in c.title.lower() and (status is None or c.status == status)
            ),
            key=lambda c: (c.title, str(c.id)),
        )

    def list_courses(self, search, status, limit, offset):
        return tuple(self._matching(search, status)[offset : offset + limit])

    def count_courses(self, search, status):
        return len(self._matching(search, status))

    def list_by_owner(self, owner_id, search, status, limit, offset):
        items = [c for c in self._matching(search, status) if c.owner_id == owner_id]
        return tuple(items[offset : offset + limit])

    def count_by_owner(self, owner_id, search, status):
        return len([c for c in self._matching(search, status) if c.owner_id == owner_id])

    def add(self, course):
        self.items[str(course.id)] = course

    def save(self, course):
        self.require_by_id(course.id)
        self.items[str(course.id)] = course

    def delete(self, course):
        del self.items[str(course.id)]


class RecordingStorage:
    def __init__(self, uow):
        self.calls = []
        self.uow = uow

    def upload_url(self, object_name, content_type, size):
        assert self.uow.exited
        self.calls.append((object_name, content_type, size))
        return "https://storage.example/upload"

    def download_url(self, object_name):
        assert self.uow.exited
        self.calls.append(object_name)
        return "https://storage.example/download"


class RecordingUnitOfWork:
    def __init__(self, repository):
        self.repository = repository
        self.commits = 0
        self.rollbacks = 0
        self.exited = False

    def __enter__(self):
        self.snapshot = dict(self.repository.items)
        self.exited = False
        return self

    def __exit__(self, exception_type, exception, traceback):
        if exception_type:
            self.rollback()
        self.exited = True

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.repository.items = self.snapshot
        self.rollbacks += 1
