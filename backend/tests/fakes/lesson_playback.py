from dataclasses import replace

from app.courses.domain.animation import AnimationProject


class RecordingLessonPlayback:
    def __init__(self, uow):
        self.uow = uow
        self.ready = False
        self.calls = []

    def video_ready(self, animation):
        assert self.uow.exited
        self.calls.append(("ready", animation))
        return self.ready

    def preview(self, animation):
        assert self.uow.exited
        self.calls.append(("preview", animation))
        return "<html>code preview</html>"


class ProgressiveAnimator:
    def __init__(self, during_delivery):
        self.during_delivery = during_delivery
        self.inputs = []
        self.error = None

    def generate(self, request):
        self.inputs.append(request)
        project = AnimationProject(
            request.plan.lesson_id,
            "a" * 64,
            "a" * 64 + "/javascript",
            "b" * 64,
            "test",
            request.alignment.duration_sec,
            review_status="pending",
        )
        request.source_ready(project)
        self.during_delivery(project)
        if self.error:
            raise self.error
        return replace(project, review_status="skipped")

    def verify(self, project):
        pass


class UnserializableProgressSink:
    def __call__(self, project):
        pass

    def __deepcopy__(self, memo):
        raise AssertionError("Progress dependencies must never enter persisted inputs")
