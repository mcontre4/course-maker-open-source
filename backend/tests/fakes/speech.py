import io
import wave

from app.courses.domain.speech import MeasuredSpeech, TimedText
from app.courses.ports.speech import SpeechArtifactUnavailable, SpeechUnavailable, SynthesizedSpeech


def speech_result(text):
    pcm = b"\x01\x00" * (240 * len(text))
    measured = MeasuredSpeech(
        pcm,
        24000,
        tuple(TimedText(c, i / 100, (i + 1) / 100) for i, c in enumerate(text)),
        "test-request",
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(pcm)
    return SynthesizedSpeech(measured, buffer.getvalue())


class RecordingSpeech:
    def __init__(self, uow):
        self.uow = uow
        self.calls = []
        self.fail_on_call = None
        self.on_call = None

    def synthesize(self, text, settings):
        assert self.uow.exited, "Do not generate speech inside a database transaction"
        self.calls.append((text, settings))
        if self.on_call:
            self.on_call()
        if self.fail_on_call == len(self.calls):
            raise SpeechUnavailable("Provider temporarily unavailable")
        return speech_result(text)


class InMemorySpeechArtifacts:
    def __init__(self, uow):
        self.uow = uow
        self.objects = {}
        self.scenes = {}
        self.fail = False

    def read(self, key):
        assert self.uow.exited
        return self.objects.get(key)

    def write(self, key, content, content_type):
        assert self.uow.exited
        if self.fail:
            raise SpeechArtifactUnavailable("Storage unavailable")
        self.objects[key] = content

    def read_scene(self, key):
        assert self.uow.exited
        return self.scenes.get(key)

    def write_scene(self, key, scene):
        assert self.uow.exited
        self.scenes[key] = scene
