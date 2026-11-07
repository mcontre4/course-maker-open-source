from app.courses.domain.animation import AnimationProject


class RecordingAnimator:
    def __init__(self, uow):
        self.uow = uow
        self.calls = []
        self.error = None
        self.on_generate = lambda: None

    def generate(self, request):
        assert self.uow.exited
        self.calls.append(request)
        self.on_generate()
        if self.error:
            raise self.error
        return AnimationProject(
            request.plan.lesson_id,
            "a" * 64,
            "a" * 64 + "/hyperframes",
            "b" * 64,
            request.animator_model.value if request.animator_model else "test-model",
            request.alignment.duration_sec,
            backend=request.animation_backend.value,
        )

    def verify(self, project):
        pass
