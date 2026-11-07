"""Single-agent, plain-JavaScript visual authoring with a versioned style package."""

import fcntl
import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

from pydantic import TypeAdapter

from app.courses.adapters.ai.animation_project import (
    preflight,
    project_digest,
    reject_symlinks,
    timing_manifest,
)
from app.courses.adapters.ai.animator import AnimationWorker
from app.courses.application.generate_storyboard import artifact_hash
from app.courses.domain.animation import AnimationProject
from app.courses.domain.visual_style import VisualStyle
from app.courses.ports.animator import AnimationInput, AnimationUnavailable


class CanvasAnimator(AnimationWorker):
    def generate(self, request: AnimationInput) -> AnimationProject:
        try:
            return self._generate_canvas(request)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise AnimationUnavailable(
                "JavaScript authoring failed; inspect the private job logs and retry"
            ) from exc

    def _generate_canvas(self, request: AnimationInput) -> AnimationProject:
        preflight(request)
        VisualStyle(request.visual_style_id, request.visual_style_version)
        style = self._tools / "styles" / request.visual_style_id
        resources = [
            *style.rglob("*"),
            *(self._tools / "canvas-template").rglob("*"),
            self._tools / "validate-canvas.mjs",
            self._tools / "render-canvas.mjs",
            self._tools / "package-lock.json",
        ]
        inputs = asdict(replace(request, source_ready=None))
        inputs.pop("source_ready")
        inputs.pop("audio")
        inputs.pop("review_output")
        inputs.pop("existing_project")
        inputs.pop("animator_model")
        prompt_file = "canvas_repair_prompt.md" if request.visual_feedback else "canvas_prompt.md"
        digest = artifact_hash(
            {
                "inputs": inputs,
                "model": self._model,
                "arguments": self._authoring_identity(prompt_file),
                "adapter": Path(__file__).read_text(),
                "fallback": Path(__file__).with_name("animation_fallback.py").read_text(),
                "image": self._image,
                "resources": {
                    str(p.relative_to(self._tools)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in resources
                    if p.is_file()
                },
            }
        )
        job, state = self._root / digest, self._root / ".state" / digest
        job.mkdir(parents=True, exist_ok=True, mode=0o700)
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        reject_symlinks(job)
        reject_symlinks(state)
        with (state / "lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AnimationUnavailable("This animation is already running") from exc
            result = state / "result.json"
            if result.exists():
                project = TypeAdapter(AnimationProject).validate_json(result.read_bytes())
                if (
                    project.input_hash != digest
                    or project.lesson_id != request.plan.lesson_id
                    or project.model != self._model
                    or project.backend != request.animation_backend.value
                    or project.prepare_elements != request.prepare_elements
                ):
                    raise AnimationUnavailable("Saved animation does not match this input version")
                self.verify(project)
                return project
            if not self._key:
                raise AnimationUnavailable("Configure OpenRouter for animation generation")
            project_dir = job / "javascript"
            # A failed worker may have left edited trusted files or extra outputs.
            # Rebuild the trusted package; retain only its unfinished drawing source.
            unfinished = project_dir / "animation.js"
            draft = (
                unfinished.read_bytes()
                if unfinished.is_file() and unfinished.stat().st_size <= 600000
                else None
            )
            if project_dir.exists():
                shutil.rmtree(project_dir)
            shutil.copytree(self._tools / "canvas-template", project_dir, dirs_exist_ok=True)
            shutil.copytree(style, project_dir / "style", dirs_exist_ok=True)
            (project_dir / "audio").mkdir(exist_ok=True)
            for scene, audio in zip(request.alignment.scenes, request.audio, strict=True):
                (project_dir / "audio" / f"{scene.scene_id}.wav").write_bytes(audio)
            (project_dir / "fonts").mkdir(exist_ok=True)
            for name, weight in (
                ("nunito", 900),
                ("nunito", 700),
                ("fredoka", 600),
                ("caveat", 400),
                ("caveat", 700),
                ("inter", 300),
                ("inter", 400),
                ("inter", 500),
                ("inter", 600),
                ("inter", 800),
                ("space-grotesk", 400),
                ("space-grotesk", 500),
                ("space-grotesk", 700),
                ("permanent-marker", 400),
                ("kalam", 700),
                ("bangers", 400),
                ("archivo-black", 400),
                ("space-mono", 400),
                ("space-mono", 700),
                ("bebas-neue", 400),
                ("oswald", 400),
                ("oswald", 700),
                ("fredoka", 700),
                ("rubik-mono-one", 400),
                ("syne", 800),
            ):
                font = f"{name}-latin-{weight}-normal.woff2"
                shutil.copyfile(
                    self._tools / "node_modules/@fontsource" / name / "files" / font,
                    project_dir / "fonts" / font,
                )
            (project_dir / "timeline.json").write_text(
                json.dumps(timing_manifest(request), indent=2)
            )
            (job / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2))
            protected = {p: p.read_bytes() for p in project_dir.rglob("*") if p.is_file()}
            protected[job / "inputs.json"] = (job / "inputs.json").read_bytes()
            if request.previous_project_key:
                previous = self._root / request.previous_project_key
                reject_symlinks(previous)
                shutil.copyfile(previous / "animation.js", project_dir / "animation.js")
            elif draft is not None:
                (project_dir / "animation.js").write_bytes(draft)
            feedback = request.visual_feedback
            (job / "change-request.json").unlink(missing_ok=True)
            if (job / "preview").exists():
                shutil.rmtree(job / "preview")
            self._author(
                job,
                prompt_file,
                "Repair the existing javascript/animation.js in one consolidated pass.\n" + feedback
                if request.visual_feedback
                else "Read inputs.json and javascript/style/STYLE.md. Author a complete "
                "renderable lesson in javascript/animation.js, including visualPlan, "
                "cueEvents and scoreSound. Run the source validator; the platform renders "
                "and a separate agent performs visual inspection.\n" + feedback,
                "repair-0" if request.visual_feedback else "author-0",
            )
            from app.courses.adapters.ai.animation_fallback import BEST_EFFORT

            self._resolve_change_request(
                request,
                job,
                lambda: self._author(job, prompt_file, BEST_EFFORT, "author-best-effort"),
            )
            try:
                reject_symlinks(job)
                if any(not p.is_file() or p.read_bytes() != data for p, data in protected.items()):
                    raise AnimationUnavailable(
                        "Animation agent changed protected style or narration"
                    )
                generated = project_dir / "animation.js"
                if not generated.is_file() or generated.stat().st_size > 600000:
                    raise AnimationUnavailable("Missing or oversized JavaScript animation")
                unexpected = (
                    {p for p in project_dir.rglob("*") if p.is_file()}
                    - set(protected)
                    - {generated}
                )
                if unexpected:
                    raise AnimationUnavailable("Only animation.js may be authored in the project")
                self.run_job(
                    job,
                    "validate",
                    ["node", "/opt/animator/validate-canvas.mjs", "/workspace/javascript"],
                    None,
                    "validate-0",
                )
                project = AnimationProject(
                    request.plan.lesson_id,
                    digest,
                    digest + "/javascript",
                    project_digest(project_dir),
                    self._model,
                    request.alignment.duration_sec,
                    backend=request.animation_backend.value,
                    session_id=(job / "agent-session-id").read_text()
                    if (job / "agent-session-id").is_file()
                    else None,
                    owner_id=request.session.owner_id if request.session else None,
                    job_id=request.session.job_id if request.session else None,
                    prepare_elements=request.prepare_elements,
                )
                result.write_text(json.dumps(asdict(project), indent=2))
                (job / "result.json").write_text(result.read_text())
                return project
            except (AnimationUnavailable, OSError, ValueError) as exc:
                raise AnimationUnavailable(
                    "JavaScript animation failed: " + str(exc)[-2000:]
                ) from exc

    def _authoring_identity(self, prompt_file: str) -> list[str]:
        raise NotImplementedError("Supply a direct LLM author")

    def _author(self, job: Path, prompt_file: str, prompt: str, name: str) -> None:
        raise NotImplementedError("Supply a direct LLM author")
