from app.courses.domain.errors import CourseConflict, CourseNotFound


class InMemoryAgentSessions:
    def __init__(self):
        self.items = {}

    def require_by_id(self, session_id):
        try:
            return self.items[str(session_id)]
        except KeyError as exc:
            raise CourseNotFound("Agent session not found") from exc

    def add(self, session):
        assert str(session.id) not in self.items
        self.items[str(session.id)] = session

    def save(self, session, expected_revision):
        if self.require_by_id(session.id).revision != expected_revision:
            raise CourseConflict("Agent session changed concurrently")
        self.items[str(session.id)] = session


class SessionUnitOfWork:
    def __init__(self, sessions):
        self.sessions = sessions
        self.active = False
        self.fail_commit = False

    def __enter__(self):
        self.active = True
        self.snapshot = self.sessions.items.copy()
        return self

    def __exit__(self, kind, error, traceback):
        if kind:
            self.rollback()
        self.active = False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("Commit failed")

    def rollback(self):
        self.sessions.items = self.snapshot
