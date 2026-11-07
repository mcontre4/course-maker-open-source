import os
import tempfile
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from google.api_core.exceptions import GoogleAPIError, NotFound, PreconditionFailed
from google.auth.exceptions import GoogleAuthError
from google.cloud.storage import Client  # type: ignore[import-untyped]
from pydantic import TypeAdapter, ValidationError

from app.courses.domain.speech import AlignedScene
from app.courses.ports.speech import SpeechArtifactUnavailable


class SceneCheckpointCodec:
    def read(self, key: str) -> bytes | None:
        raise NotImplementedError

    def write(self, key: str, content: bytes, content_type: str) -> None:
        raise NotImplementedError

    def read_scene(self, key: str) -> AlignedScene | None:
        value = self.read(key)
        if value is None:
            return None
        try:
            return TypeAdapter(AlignedScene).validate_json(value)
        except (ValidationError, ValueError) as exc:
            raise SpeechArtifactUnavailable("Invalid saved speech checkpoint") from exc

    def write_scene(self, key: str, scene: AlignedScene) -> None:
        import json

        self.write(key, json.dumps(asdict(scene), sort_keys=True).encode(), "application/json")


class LocalSpeechArtifacts(SceneCheckpointCodec):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise SpeechArtifactUnavailable("Invalid speech artifact key")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise SpeechArtifactUnavailable("Speech artifact escapes the private storage root")
        return path

    def read(self, key: str) -> bytes | None:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise SpeechArtifactUnavailable("Cannot read local speech artifact") from exc

    def write(self, key: str, content: bytes, content_type: str) -> None:
        try:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                    # Immutable content keys; races must not replace an existing object.
                    os.link(temporary, path)
                except FileExistsError:
                    if path.read_bytes() != content:
                        raise SpeechArtifactUnavailable("Speech artifact version already exists")
                finally:
                    temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise SpeechArtifactUnavailable("Cannot persist local speech artifact") from exc


class GcsSpeechArtifacts(SceneCheckpointCodec):
    def __init__(self, client: Client, bucket: str) -> None:
        self._bucket = client.bucket(bucket)

    def read(self, key: str) -> bytes | None:
        try:
            return bytes(self._bucket.blob(key).download_as_bytes(timeout=30))
        except NotFound:
            return None
        except (GoogleAPIError, GoogleAuthError) as exc:
            raise SpeechArtifactUnavailable("Cannot read GCS speech artifact") from exc

    def write(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self._bucket.blob(key).upload_from_string(
                content,
                content_type=content_type,
                if_generation_match=0,
                timeout=60,
            )
        except PreconditionFailed as exc:
            if self.read(key) != content:
                raise SpeechArtifactUnavailable("Speech artifact version already exists") from exc
        except (GoogleAPIError, GoogleAuthError) as exc:
            raise SpeechArtifactUnavailable("Cannot persist GCS speech artifact") from exc
