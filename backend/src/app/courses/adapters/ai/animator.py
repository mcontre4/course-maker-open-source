"""Offline validation/render worker shared by direct animation adapters."""

import os
import signal
import subprocess
import time
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

from app.courses.adapters.ai.animation_project import project_digest, reject_symlinks
from app.courses.adapters.ai.spend import ProviderUsageTracking
from app.courses.domain.animation import AnimationProject
from app.courses.ports.animator import AnimationInput, AnimationUnavailable


class AnimationWorker:
    def __init__(
        self,
        root: Path,
        tools: Path,
        api_key: str,
        model: str = "openai/gpt-6.1-sol",
        image: str = "course-maker-animator:canvas-v1",
        timeout_sec: int = 900,
        max_attempts: int = 2,
        *,
        tracking: ProviderUsageTracking | None = None,
        reasoning_effort: str = "medium",
        command_runner: Callable[[Path, str, list[str], str | None, str], None] | None = None,
    ) -> None:
        self._tracking = tracking
        self._root, self._tools = root.resolve(), tools.resolve()
        self._key, self._model, self._image = api_key, model, image
        self._timeout, self._attempts = timeout_sec, max_attempts
        self._execute = command_runner or self._run
        self._reasoning_effort = reasoning_effort
        if not 1 <= max_attempts <= 3 or not 60 <= timeout_sec <= 1800:
            raise ValueError("Invalid animator execution limits")

    def _resolve_change_request(
        self, request: AnimationInput, job: Path, retry: Callable[[], None]
    ) -> None:
        from app.courses.adapters.ai.animation_fallback import write_fallback

        path = job / "change-request.json"
        if not path.exists():
            return
        reject_symlinks(job)
        sources = (
            [job / "javascript/animation.js"]
            if (job / "javascript").is_dir()
            else [
                job / "remotion/scene-manifest.json",
                job / "remotion/IMPLEMENTATION.md",
                *[job / f"remotion/src/scenes/{s.scene_id}.tsx" for s in request.storyboard.scenes],
            ]
        )
        path.unlink()
        # An advisory request must never discard an existing complete draft.
        if all(p.is_file() for p in sources):
            return
        try:
            retry()
        except AnimationUnavailable:
            # A failed continuation must not turn missing visual resources into a blocker.
            pass
        reject_symlinks(job)
        path.unlink(missing_ok=True)
        if not all(p.is_file() for p in sources):
            write_fallback(request, job)

    def verify(self, project: AnimationProject) -> None:
        path = self._root / project.project_key
        if (
            path.is_symlink()
            or path.parent.is_symlink()
            or not path.is_dir()
            or any(p.is_symlink() for p in path.rglob("*"))
        ):
            raise AnimationUnavailable("Saved animation project is missing or unsafe")
        if project_digest(path) != project.output_hash:
            raise AnimationUnavailable("Saved animation project checksum mismatch")

    def run_job(self, job: Path, kind: str, args: list[str], prompt: str | None, name: str) -> None:
        with (
            self._tracking.worker("render")
            if self._tracking is not None and name.startswith("render-")
            else nullcontext()
        ):
            self._execute(job, kind, args, prompt, name)

    def _run(
        self,
        job: Path,
        kind: str,
        args: list[str],
        prompt: str | None,
        name: str,
    ) -> None:
        if not (
            kind == "validate"
            and args
            and args[0] in {"node", "python3"}
            and len(args) >= 2
            and args[1]
            in {
                "/opt/animator/validate-project.mjs",
                "/opt/animator/compile-assets.py",
                "/opt/animator/review-project.mjs",
                "/opt/animator/validate-canvas.mjs",
                "/opt/animator/render-canvas.mjs",
            }
        ):
            raise AnimationUnavailable("Unsupported animation worker command")
        logs = job / "logs"
        logs.mkdir(exist_ok=True)
        container = "animator-" + job.name[:20] + "-" + name
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container,
            "--init",
            "-i",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=512",
            "--memory=4g",
            "--cpus=2",
            "--tmpfs=/tmp:rw,nosuid,size=1g",
            "--shm-size=512m",
            "--mount",
            f"type=bind,source={job},target=/workspace",
        ]
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "DOCKER_HOST"}}
        command += ["--network=none"]
        budget = self._timeout
        # A worker-side deadline still applies if the Docker client disappears.
        command += [
            "--entrypoint",
            "/bin/sh",
            self._image,
            "-c",
            'mkdir -p /tmp/home; exec timeout "$@"',
            "--",
            "--kill-after=5s",
            f"{budget}s",
            *args,
        ]
        with (logs / f"{name}.log").open("w") as log:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + budget + 10
                input_text = prompt
                while True:
                    try:
                        process.communicate(
                            input_text, timeout=min(2, max(0.01, deadline - time.monotonic()))
                        )
                        break
                    except subprocess.TimeoutExpired:
                        input_text = None
                        if time.monotonic() >= deadline:
                            raise
            except subprocess.TimeoutExpired as exc:
                try:
                    subprocess.run(["docker", "kill", container], capture_output=True, timeout=15)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                raise AnimationUnavailable("Animation runtime exceeded its time budget") from exc
        if process.returncode:
            raise AnimationUnavailable(
                f"{kind} failed: " + (logs / f"{name}.log").read_text()[-6000:]
                if kind == "validate"
                else f"{kind} failed; inspect logs/{name}.log"
            )
