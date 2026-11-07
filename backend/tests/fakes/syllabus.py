from dataclasses import replace

from fakes.courses import RecordingUnitOfWork

from app.courses.domain.errors import CourseConflict
from app.courses.ports.syllabus_agent import SyllabusAgentResponse


class InMemoryConversations:
    def __init__(self):
        self.items = {}

    def get_by_course_id(self, course_id):
        return self.items.get(str(course_id))

    def save(self, conversation, expected_revision):
        current = self.items.get(conversation.course_id)
        if (current.revision if current else 0) != expected_revision:
            raise CourseConflict("Conversation changed")
        self.items[conversation.course_id] = conversation


class SyllabusUnitOfWork(RecordingUnitOfWork):
    def __init__(self, courses, conversations):
        super().__init__(courses)
        self.conversations = conversations
        self.fail_commit = False

    def __enter__(self):
        super().__enter__()
        self.conversation_snapshot = dict(self.conversations.items)
        return self

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("Commit failed")
        super().commit()

    def rollback(self):
        super().rollback()
        self.conversations.items = self.conversation_snapshot


class RecordingSyllabusAgent:
    def __init__(self, plan, uow):
        self.plan, self.uow = plan, uow
        self.requests = []
        self.error = None
        self.during_run = None
        self.session_id = None

    def run(self, request):
        assert self.uow.exited, "No transaction may span an external API call"
        self.requests.append(request)
        if self.error:
            raise self.error
        if self.during_run:
            self.during_run()
        return SyllabusAgentResponse(
            "Updated syllabus",
            self.plan,
            request.history_json + " next turn",
            self.session_id,
        )


def rename_course(courses, course_id):
    course = courses.require_by_id(course_id)
    courses.save(replace(course, title="Concurrent edit"))
