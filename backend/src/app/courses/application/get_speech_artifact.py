import hashlib
import json
from dataclasses import asdict, dataclass

from app.courses.domain.errors import ContentNotReady, CourseNotFound
from app.courses.domain.identifiers import CourseId
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.speech import SpeechArtifacts, SpeechArtifactUnavailable
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class GetSpeechArtifactRequest:
    course_id: str
    lesson_id: str
    kind: str
    scene_id: str | None = None


@dataclass(frozen=True)
class SpeechArtifactResponse:
    content: bytes
    content_type: str


class GetSpeechArtifact:
    def __init__(
        self, courses: CourseRepository, artifacts: SpeechArtifacts, uow: UnitOfWork
    ) -> None:
        self._courses, self._artifacts, self._uow = courses, artifacts, uow

    def execute(self, request: GetSpeechArtifactRequest) -> SpeechArtifactResponse:
        with self._uow:
            lesson = self._courses.require_by_id(CourseId(request.course_id)).lesson(
                request.lesson_id
            )
            alignment = lesson.alignment
            if alignment is None:
                raise ContentNotReady(
                    "Generate aligned narration before retrieving speech artifacts"
                )
        checksum: str | None = None
        if request.kind == "alignment":
            key, content_type = alignment.alignment_key, "application/json"
        elif request.kind == "transcript":
            key = alignment.alignment_key.removesuffix("alignment.json") + "transcript.txt"
            content_type = "text/plain; charset=utf-8"
        elif request.kind == "audio":
            scene = next((s for s in alignment.scenes if s.scene_id == request.scene_id), None)
            if scene is None:
                raise CourseNotFound("Speech scene not found")
            key, content_type = scene.audio_key, "audio/wav"
            checksum = scene.audio_sha256
        else:
            raise CourseNotFound("Speech artifact not found")
        content = self._artifacts.read(key)
        if content is None:
            raise SpeechArtifactUnavailable("Saved speech artifact is missing from storage")
        if checksum is not None and hashlib.sha256(content).hexdigest() != checksum:
            raise SpeechArtifactUnavailable("Saved speech audio is corrupt")
        if (
            request.kind == "transcript"
            and content != "\n\n".join(s.transcript for s in alignment.scenes).encode()
        ):
            raise SpeechArtifactUnavailable("Saved speech transcript is corrupt")
        if request.kind == "alignment":
            try:
                matches = json.loads(content) == json.loads(json.dumps(asdict(alignment)))
            except (ValueError, UnicodeDecodeError):
                matches = False
            if not matches:
                raise SpeechArtifactUnavailable("Saved speech alignment is corrupt")
        return SpeechArtifactResponse(content, content_type)
