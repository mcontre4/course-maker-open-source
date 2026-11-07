from threading import Event

from fakes.lesson_agent import SuccessfulLessonAgent
from fixtures.storyboard import storyboard

from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.ports.storyboard_agent import StoryboardAgentResponse


class GenerationGate:
    def __init__(self):
        self.entered, self.finish = Event(), Event()
        self.finish.set()

    def block(self):
        self.entered.clear()
        self.finish.clear()

    def wait(self):
        self.entered.set()
        assert self.finish.wait(15), "Test must release the provider"


class GatedLessonAgent(SuccessfulLessonAgent):
    def __init__(self):
        super().__init__()
        self.gate = GenerationGate()
        self.error = None

    def run(self, request):
        self.gate.wait()
        if self.error:
            raise self.error
        return super().run(request)


class GatedStoryboardAgent:
    def __init__(self):
        self.gate = GenerationGate()
        self.calls = []

    def run(self, request):
        self.calls.append(request)
        self.gate.wait()
        return StoryboardAgentResponse(
            storyboard(request.plan, request.target_video_minutes),
            PlanGeneration("test-model", 1, 0, 1000),
        )


class GatedThumbnails:
    def __init__(self):
        self.gate = GenerationGate()

    def generate(self, title, description, topics=(), *, visual_direction=""):
        self.gate.wait()
        return "generated-thumbnail"
