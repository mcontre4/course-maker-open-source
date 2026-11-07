from fixtures.storyboard import storyboard

from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.ports.storyboard_agent import StoryboardAgentResponse


class RecordingStoryboardAgent:
    def __init__(self, uow):
        self.uow = uow
        self.calls = []
        self.error = None
        self.during_run = None
        self.output = None

    def run(self, request):
        assert self.uow.exited, "External calls must happen outside a transaction"
        self.calls.append(request)
        if self.error:
            raise self.error
        if self.during_run:
            self.during_run()
        return StoryboardAgentResponse(
            self.output or storyboard(request.plan, request.target_video_minutes),
            PlanGeneration("test-model", 1, 0, 1000),
        )
