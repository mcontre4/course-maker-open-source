from datetime import UTC, datetime, timedelta
from threading import Event

from app.courses.domain.errors import CourseNotFound
from app.courses.domain.lesson_interactive import InteractiveDetails, InteractivePage

HTML = """<!doctype html><html lang="en"><head><meta name="viewport"
content="width=device-width, initial-scale=1"><title>Gravity lab</title>
<style>body{font:16px system-ui;margin:16px}button{padding:12px}</style></head>
<body><h1>Gravity lab</h1><button id="try">Change gravity</button><output>9.8</output>
<script>document.querySelector('button').onclick=()=>{
document.querySelector('output').textContent='1.6';};</script></body></html>"""


def interactive_page(label="Gravity lab"):
    return InteractivePage(
        HTML.replace("Gravity lab", label),
        InteractiveDetails(label, "Explore gravity.", ("Change gravity.", "Reset the experiment.")),
    )


class InMemoryInteractiveLessons:
    def __init__(self, *lessons):
        self.items = {str(lesson.content.id): lesson for lesson in lessons}

    def require_by_id(self, lesson_id):
        if str(lesson_id) not in self.items:
            raise CourseNotFound("Lesson not found")
        return self.items[str(lesson_id)]

    def require_for_change(self, lesson_id):
        return self.require_by_id(lesson_id)


class InMemoryLessonInteractives:
    def __init__(self):
        self.items = {}
        self.order = {}

    def list_by_lesson_id(self, lesson_id):
        ids = self.order.get(str(lesson_id), ())
        return tuple(self.items[i] for i in ids if i in self.items)

    def get_by_id(self, identifier):
        return self.items.get(str(identifier))

    def add(self, item, lesson):
        self.items[str(item.id)] = item
        self.order.setdefault(str(item.lesson_id), []).append(str(item.id))

    def save(self, item):
        self.items[str(item.id)] = item

    def delete(self, item):
        del self.items[str(item.id)]
        self.order[str(item.lesson_id)].remove(str(item.id))

    def reorder(self, lesson_id, identifiers):
        self.order[str(lesson_id)] = [str(i) for i in identifiers]


class InteractiveClock:
    def __init__(self):
        self.value = datetime(2026, 11, 1, tzinfo=UTC)

    def now(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class RecordingInteractiveJobs:
    def __init__(self):
        self.jobs = []
        self.error = None

    def enqueue(self, job):
        if self.error:
            raise self.error
        self.jobs.append(job)


class RecordingInteractiveAgent:
    def __init__(self, uow=None):
        self.uow, self.calls = uow, []
        self.during_run = None
        self.error = None
        self.page = interactive_page()

    def run(self, request):
        if self.uow:
            assert self.uow.exited, "AI calls must run outside transactions"
        self.calls.append(request)
        if self.during_run:
            self.during_run()
        if self.error:
            raise self.error
        return self.page


class BlockingInteractiveAgent(RecordingInteractiveAgent):
    def __init__(self):
        super().__init__()
        self.started, self.release = Event(), Event()

    def run(self, request):
        self.started.set()
        if not self.release.wait(timeout=15):
            raise TimeoutError("Test did not release the interactive agent")
        return super().run(request)
