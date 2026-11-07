from fixtures.lesson_plan import lesson_plan

from app.courses.ports.lesson_agent import LessonAgentResponse


class SuccessfulLessonAgent:
    """Deterministic provider boundary for tests using the real persistence wiring."""

    def __init__(self):
        self.calls = []

    def run(self, request):
        self.calls.append(request)
        return LessonAgentResponse(lesson_plan(request.brief), "test-model", 2, 1, 100)


class RecordingLessonAgent:
    def __init__(self, uow):
        self.uow = uow
        self.calls = []
        self.error = None
        self.during_run = None
        self.plan = None

    def run(self, request):
        assert self.uow.exited, "External calls must happen outside a transaction"
        self.calls.append(request)
        if self.error:
            raise self.error
        if self.during_run:
            self.during_run()
        return LessonAgentResponse(self.plan or lesson_plan(request.brief), "test-model", 2, 1, 100)
