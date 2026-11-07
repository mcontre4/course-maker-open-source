"""Deterministic outgoing ports for the complete lesson browser journey."""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

from fakes.speech import InMemorySpeechArtifacts, RecordingSpeech
from fakes.storyboard_agent import RecordingStoryboardAgent

from app.courses.domain.animation import AnimationProject
from app.courses.domain.speech import SpeechSettings
from app.courses.ports.animator import AnimationUnavailable
from app.courses.ports.style import VoiceOption


class BrowserLessonMedia:
    def __init__(self, fixture: Path):
        probe = SimpleNamespace(exited=True)
        self.storyboard = RecordingStoryboardAgent(probe)
        self.speech = (
            RecordingSpeech(probe),
            InMemorySpeechArtifacts(probe),
            SpeechSettings("test-voice"),
            0.0,
        )
        self.video = fixture.read_bytes()
        self.failed = set()

    def generate(self, request):
        if any("retry once" in objective.lower() for objective in request.plan.objectives):
            if request.plan.lesson_id not in self.failed:
                self.failed.add(request.plan.lesson_id)
                raise AnimationUnavailable(
                    "Animation interrupted. Your script and narration are saved."
                )
        key = hashlib.sha256(
            json.dumps(
                {
                    "script": asdict(request.storyboard),
                    "alignment": asdict(request.alignment),
                    "style": request.visual_style,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        project = AnimationProject(
            request.plan.lesson_id,
            key,
            key + "/javascript",
            hashlib.sha256((key + ":video").encode()).hexdigest(),
            "browser-test",
            request.alignment.duration_sec,
            review_status="skipped",
        )
        if request.source_ready:
            request.source_ready(replace(project, review_status="pending"))
        return project

    def verify(self, project):
        pass

    def list(self):
        return (VoiceOption("test-voice", "Test narrator", labels=("accent:American",)),)

    def read(self, project):
        return self.video

    def video_ready(self, project):
        return project.review_status != "pending"

    def preview(self, project):
        return "<html><body>Animation preview</body></html>"
