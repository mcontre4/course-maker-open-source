"""Cached H.264 playback, rendered without network or provider credentials."""

import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.courses.adapters.ai.animation_project import project_digest
from app.courses.domain.animation import AnimationProject
from app.courses.ports.lesson_video import LessonVideoUnavailable


class LocalLessonVideo:
    def __init__(self, directory: Path, image: str, timeout: int = 1800) -> None:
        self._directory, self._image, self._timeout = directory.resolve(), image, timeout

    def read(self, animation: AnimationProject) -> bytes:
        try:
            ready = self.read_ready(animation)
            if ready is not None:
                return ready
            if animation.review_status != "legacy":
                raise LessonVideoUnavailable("Validated video is missing; regenerate the video")
            # Include the renderer version so changes never reuse incompatible media.
            key = hashlib.sha256((animation.output_hash + self._image).encode()).hexdigest()
            cache = self._directory / ".playback" / key
            cache.mkdir(parents=True, exist_ok=True)
            output = cache / "lesson.mp4"
            with (cache / "render.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if not output.is_file():
                    self._render(self._directory / animation.project_key, cache, output)
                try:
                    return output.read_bytes()
                except OSError as exc:
                    raise LessonVideoUnavailable(
                        "The saved video could not be read. Retry playback."
                    ) from exc
        except OSError as exc:
            raise LessonVideoUnavailable(
                "Saved playback storage is unavailable. Retry playback."
            ) from exc

    def read_ready(self, animation: AnimationProject) -> bytes | None:
        """Inspect completed artifacts only; never start or wait for an encoder."""
        try:
            if not re.fullmatch(r"[0-9a-f]{64}/(?:remotion|javascript)", animation.project_key):
                raise LessonVideoUnavailable("This animation format cannot be played yet")
            project = self._directory / animation.project_key
            if (
                not project.is_dir()
                or project.is_symlink()
                or not project.resolve().is_relative_to(self._directory)
                or any(p.is_symlink() for p in project.rglob("*"))
            ):
                raise LessonVideoUnavailable("The saved animation source is missing or invalid")
            if project_digest(project) != animation.output_hash:
                raise LessonVideoUnavailable("The saved animation source checksum does not match")
            # Reuse a completed, technically verified video, including advisory-review fallbacks.
            for decision in (self._directory / ".review-state").glob("*/result.json"):
                try:
                    report = json.loads(decision.read_text())
                    if (
                        not isinstance(report, dict)
                        or not (
                            report.get("approved") is True
                            or (
                                animation.review_status in {"skipped", "pending", "warning"}
                                and report.get("review_status") == "skipped"
                                and report.get("validation") == "technical_validated"
                            )
                            or (
                                animation.review_status in {"repaired", "pending"}
                                and report.get("review_status") == "repaired"
                                and report.get("validation") == "visual_repaired"
                            )
                        )
                        or report.get("source_hash") != animation.output_hash
                        or report.get("renderer_version") != self._image
                    ):
                        continue
                    key = report.get("video_key", "")
                    if not isinstance(key, str) or not re.fullmatch(
                        r"\.reviews/[0-9a-f]{64}/render/lesson\.mp4", key
                    ):
                        continue
                    video = self._directory / key
                    if video.is_symlink() or not video.resolve().is_relative_to(self._directory):
                        continue
                    content = video.read_bytes()
                    if hashlib.sha256(content).hexdigest() == report.get("video_sha256"):
                        return content
                except (OSError, ValueError, TypeError):
                    continue
            if animation.review_status == "legacy":
                key = hashlib.sha256((animation.output_hash + self._image).encode()).hexdigest()
                cached = self._directory / ".playback" / key / "lesson.mp4"
                if cached.is_file() and not cached.is_symlink():
                    return cached.read_bytes()
            return None
        except OSError as exc:
            raise LessonVideoUnavailable("Saved playback storage is unavailable") from exc

    def _render(self, project: Path, cache: Path, output: Path) -> None:
        # Docker sibling mounts require the same absolute host/container paths.
        with tempfile.TemporaryDirectory(prefix="render-", dir=cache) as work:
            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                "lesson-video-" + hashlib.sha256(str(cache).encode()).hexdigest()[:24],
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--cpus=2",
                "--memory=2g",
                "--pids-limit=256",
                "--shm-size=512m",
                "--tmpfs=/tmp:rw,size=1g",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--mount",
                f"type=bind,src={project},dst=/source,readonly",
                "--mount",
                f"type=bind,src={work},dst=/output",
                self._image,
                "/source",
                "/output/lesson.mp4",
                "2",
            ]
            try:
                with (cache / "render.log").open("wb") as log:
                    subprocess.run(
                        command,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=True,
                        timeout=self._timeout,
                    )
                rendered = Path(work) / "lesson.mp4"
                if not rendered.is_file() or rendered.stat().st_size < 32:
                    raise LessonVideoUnavailable("Video rendering did not produce playable media")
                rendered.replace(output)
            except subprocess.TimeoutExpired as exc:
                try:
                    subprocess.run(
                        [
                            "docker",
                            "rm",
                            "--force",
                            "lesson-video-" + hashlib.sha256(str(cache).encode()).hexdigest()[:24],
                        ],
                        capture_output=True,
                        timeout=30,
                    )
                except (OSError, subprocess.SubprocessError):
                    # Cleanup failure must not mask the retryable playback error.
                    pass
                raise LessonVideoUnavailable(
                    "Video preparation timed out. Retry playback."
                ) from exc
            except (OSError, subprocess.SubprocessError) as exc:
                raise LessonVideoUnavailable(
                    "The video could not be prepared. Check the playback renderer and retry."
                ) from exc
