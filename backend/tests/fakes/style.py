from dataclasses import replace

from app.courses.domain.style import LessonStyle
from app.courses.ports.style import VoiceOption


class RecordingStylePlanner:
    def __init__(self, uow=None):
        self.uow = uow
        self.calls = []
        self.error = None
        self.during_run = None
        self.result = LessonStyle(
            summary="A playful, clear lesson.",
            voice_id="friendly",
            delivery="Warm, curious, encouraging",
        )

    def resolve(self, context, request, audience, voices, mode, **preferences):
        self.preferences = preferences
        if self.uow:
            assert self.uow.exited, "Style planning must not keep a transaction open"
        self.calls.append((context, request, audience, voices, mode))
        if self.during_run:
            self.during_run()
        if self.error:
            raise self.error
        return replace(self.result, request=request, audience=audience)


class FixedVoiceCatalog:
    def __init__(self):
        self.items = (
            VoiceOption(
                "friendly", "Friendly teacher", "Warm and curious", labels=("accent: American",)
            ),
            VoiceOption(
                "steady", "Steady narrator", "Measured and calm", labels=("accent: American",)
            ),
        )

    def list(self):
        return self.items
