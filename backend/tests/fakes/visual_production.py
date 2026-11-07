from app.courses.domain.animation import AnimationProject
from app.courses.ports.visual_production import VisualAssets, VisualReview


class RecordingVisualAssets:
    def __init__(self, events):
        self.events, self.requests = events, []

    def generate(self, request):
        self.events.append("assets")
        self.requests.append(request)
        return VisualAssets(".assets/" + "a" * 64 + "/assets", "b" * 64)


class RecordingCompositor:
    def __init__(self, events, repair_error=None):
        self.events, self.requests = events, []
        self.repair_error = repair_error

    def generate(self, request):
        self.events.append("animation")
        self.requests.append(request)
        if request.visual_feedback and self.repair_error is not None:
            raise self.repair_error
        digest = str(len(self.requests)) * 64
        return AnimationProject(
            request.plan.lesson_id,
            digest,
            digest + "/remotion",
            "c" * 64,
            "test",
            request.alignment.duration_sec,
            backend=request.animation_backend.value,
        )

    def verify(self, project):
        pass


class RecordingVisualReview:
    def __init__(self, events):
        self.events, self.projects = events, []
        self.decisions = [VisualReview(True, "Readable and well composed")]

    def review(self, project):
        self.events.append("review")
        self.projects.append(project)
        return self.decisions.pop(0)
