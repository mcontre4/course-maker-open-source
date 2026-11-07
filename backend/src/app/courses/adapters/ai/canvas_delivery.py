import fcntl
import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.courses.adapters.ai.animation_project import project_digest, reject_symlinks
from app.courses.domain.animation import AnimationProject
from app.courses.ports.animator import AnimationUnavailable
from app.courses.ports.visual_production import VisualReview

CommandRunner = Callable[[Path, str, list[str], str | None, str], None]


def _repair_findings(report: dict[str, Any]) -> str:
    """Keep scene-specific fixes when projecting a review into repair instructions."""
    return json.dumps(
        {key: report[key] for key in ("feedback", "scene_checks", "quality") if key in report},
        ensure_ascii=False,
        indent=2,
    )


class CanvasDelivery:
    def __init__(
        self,
        root: Path,
        arguments: list[str],
        runner: CommandRunner,
        renderer: CommandRunner,
        renderer_version: str,
    ) -> None:
        self._root, self._arguments = root.resolve(), arguments
        self._runner, self._renderer, self._version = runner, renderer, renderer_version

    def deliver(
        self,
        project: AnimationProject,
        *,
        review: bool,
        repair_feedback: str | None = None,
        source_ready: Callable[[], None] | None = None,
    ) -> VisualReview:
        try:
            return self._deliver(
                project, review=review, repair_feedback=repair_feedback, source_ready=source_ready
            )
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise AnimationUnavailable(
                "Video delivery failed; inspect the private render logs"
            ) from exc

    def _deliver(
        self,
        project: AnimationProject,
        *,
        review: bool,
        repair_feedback: str | None,
        source_ready: Callable[[], None] | None,
    ) -> VisualReview:
        if repair_feedback is not None and (review or not repair_feedback.strip()):
            raise AnimationUnavailable("A repaired delivery requires the consolidated findings")
        status = "repaired" if repair_feedback is not None else "approved" if review else "skipped"
        if not re.fullmatch(r"[0-9a-f]{64}/javascript", project.project_key):
            raise AnimationUnavailable("Invalid JavaScript source key")
        source = self._root / project.project_key
        reject_symlinks(source)
        if project_digest(source) != project.output_hash:
            raise AnimationUnavailable("Source changed before rendering")
        revision = hashlib.sha256(
            json.dumps(
                {
                    "source": project.output_hash,
                    "reviewer_session_id": project.reviewer_session_id,
                    "owner_id": project.owner_id,
                    "job_id": project.job_id,
                    "review": review,
                    "repair_feedback": repair_feedback,
                    "renderer": self._version,
                    "arguments": self._arguments,
                    "adapter": Path(__file__).read_text(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        job, state = self._root / ".reviews" / revision, self._root / ".review-state" / revision
        job.mkdir(parents=True, exist_ok=True)
        state.mkdir(parents=True, exist_ok=True)
        reject_symlinks(job)
        reject_symlinks(state)
        with (state / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            accepted = state / "result.json"
            if accepted.exists():
                report = json.loads(accepted.read_text())
                if (
                    isinstance(report, dict)
                    and report.get("source_hash") == project.output_hash
                    and report.get("review_status") == "rejected"
                    and review
                ):
                    return VisualReview(
                        False, _repair_findings(report), session_id=report.get("session_id")
                    )
                video = job / "render/lesson.mp4"
                if (
                    isinstance(report, dict)
                    and video.is_file()
                    and not video.is_symlink()
                    and report.get("source_hash") == project.output_hash
                    and report.get("video_sha256") == hashlib.sha256(video.read_bytes()).hexdigest()
                    and report.get("review_status") == status
                ):
                    if source_ready is not None:
                        source_ready()
                    return VisualReview(
                        True, report["feedback"], session_id=report.get("session_id")
                    )
            if (job / "javascript").exists():
                shutil.rmtree(job / "javascript")
            shutil.copytree(source, job / "javascript")
            shutil.copyfile(source.parent / "inputs.json", job / "inputs.json")
            if project.owner_id:
                inputs = json.loads((job / "inputs.json").read_text())
                inputs["session"] = {
                    "owner_id": project.owner_id,
                    "resource_id": project.lesson_id,
                    "job_id": project.job_id,
                    "session_id": project.session_id,
                }
                inputs["reviewer_session_id"] = project.reviewer_session_id
                (job / "inputs.json").write_text(json.dumps(inputs))
            approved_inputs = (job / "inputs.json").read_bytes()
            # Keep the paid decision independent of the final encoder. A retry
            # after an encoding failure must not perform another visual review.
            review_record = state / "visual-review.json"
            cached_review = (
                json.loads(review_record.read_text()) if review_record.exists() else None
            )
            if not (
                isinstance(cached_review, dict)
                and cached_review.get("source_hash") == project.output_hash
                and cached_review.get("renderer_version") == self._version
            ):
                cached_review = None
            validated_render = self._reuse_render(project, job)
            trusted_video_hash = (
                hashlib.sha256((job / "render/lesson.mp4").read_bytes()).hexdigest()
                if validated_render
                else None
            )
            if not validated_render and review and cached_review is None:
                self._renderer(
                    job,
                    "validate",
                    [
                        "node",
                        "/opt/animator/render-canvas.mjs",
                        "/workspace/javascript",
                        "/workspace/render",
                        "review",
                    ],
                    None,
                    "render-review",
                )
            report = (
                cached_review
                if review and cached_review is not None
                else {
                    "approved": False,
                    "feedback": "Rendered and technically validated; awaiting your review.",
                }
            )
            if repair_feedback is not None:
                report["feedback"] = (
                    "One consolidated repair applied; final video technically verified. "
                    "No second AI review was performed. Original findings: " + repair_feedback
                )
            if review and cached_review is None:
                sheets = sorted((job / "render").glob("contact-*.png"))
                if not sheets:
                    raise AnimationUnavailable("Missing rendered visual evidence")
                (job / "review.json").unlink(missing_ok=True)
                self._runner(
                    job,
                    "direct",
                    self._arguments,
                    "Inspect all scenes and cue/transition samples in ONE consolidated review. "
                    "Read inputs.json and render/visual-plan.json; write review.json with every "
                    "material defect, its scene/timestamp and a concrete fix. Do not edit code.",
                    "visual-review",
                )
                try:
                    report = json.loads((job / "review.json").read_text())
                    if not isinstance(report, dict):
                        raise ValueError("Visual review must be an object")
                    quality = report.get("quality", {})
                    if not isinstance(quality, dict) or set(quality) != {
                        "style_fidelity",
                        "illustration",
                        "composition",
                        "continuity",
                        "explanation",
                        "visual_development",
                        "pacing",
                    }:
                        raise ValueError("Missing style quality scores")
                    if any(type(v) is not int or not 1 <= v <= 5 for v in quality.values()):
                        raise ValueError("Invalid style quality scores")
                    checks = report.get("scene_checks")
                    if not isinstance(checks, list) or any(
                        not isinstance(scene, dict)
                        or not isinstance(scene.get("observations"), str)
                        or not scene["observations"].strip()
                        for scene in checks
                    ):
                        raise ValueError("Missing scene observations")
                    expected = {
                        s["scene_id"]
                        for s in json.loads((source / "timeline.json").read_text())["scenes"]
                    }
                    if (
                        type(report["approved"]) is not bool
                        or not isinstance(report["feedback"], str)
                        or not report["feedback"].strip()
                        or {s["scene_id"] for s in checks} != expected
                    ):
                        raise ValueError("Incomplete visual review")
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    raise AnimationUnavailable("Missing or incomplete visual review") from exc
            reject_symlinks(job)
            if (
                project_digest(job / "javascript") != project.output_hash
                or (job / "inputs.json").read_bytes() != approved_inputs
            ):
                raise AnimationUnavailable("Rendered source was modified")
            if review:
                report.update(source_hash=project.output_hash, renderer_version=self._version)
                review_record.write_text(json.dumps(report, indent=2))
            if review and not report["approved"]:
                report.update(
                    source_hash=project.output_hash,
                    renderer_version=self._version,
                    review_status="rejected",
                    validation="visual_rejected",
                )
                accepted.write_text(json.dumps(report, indent=2))
                (job / "decision.json").write_text(accepted.read_text())
                return VisualReview(
                    False, _repair_findings(report), session_id=report.get("session_id")
                )
            if validated_render and trusted_video_hash is not None:
                video = job / "render/lesson.mp4"
                validated_render = (
                    video.is_file()
                    and hashlib.sha256(video.read_bytes()).hexdigest() == trusted_video_hash
                )
            # Encode the full video only after accepting the draft or applying its repair.
            if source_ready is not None:
                source_ready()
            if not validated_render:
                self._renderer(
                    job,
                    "validate",
                    [
                        "node",
                        "/opt/animator/render-canvas.mjs",
                        "/workspace/javascript",
                        "/workspace/render",
                    ],
                    None,
                    "render-final",
                )
            if project_digest(job / "javascript") != project.output_hash:
                raise AnimationUnavailable("Rendered source was modified")
            report.update(
                source_hash=project.output_hash,
                renderer_version=self._version,
                review_status=status,
                validation="visual_repaired"
                if repair_feedback is not None
                else "visual_approved"
                if review
                else "technical_validated",
                video_key=f".reviews/{revision}/render/lesson.mp4",
                video_sha256=hashlib.sha256((job / "render/lesson.mp4").read_bytes()).hexdigest(),
            )
            accepted.write_text(json.dumps(report, indent=2))
            (job / "decision.json").write_text(accepted.read_text())
            return VisualReview(
                report["approved"] if review else True,
                report["feedback"],
                session_id=report.get("session_id"),
            )

    def _reuse_render(self, project: AnimationProject, job: Path) -> bool:
        for decision in (self._root / ".review-state").glob("*/result.json"):
            try:
                report = json.loads(decision.read_text())
                if not isinstance(report, dict):
                    continue
                key = report.get("video_key", "")
                if (
                    report.get("source_hash") != project.output_hash
                    or report.get("renderer_version") != self._version
                    or report.get("validation")
                    not in {"visual_approved", "visual_repaired", "technical_validated"}
                    or not isinstance(key, str)
                    or not re.fullmatch(r"\.reviews/[0-9a-f]{64}/render/lesson\.mp4", key)
                ):
                    continue
                video = self._root / key
                reject_symlinks(video.parent)
                if hashlib.sha256(video.read_bytes()).hexdigest() != report.get("video_sha256"):
                    continue
                if not (video.parent / "verification.json").is_file():
                    continue
                destination = job / "render"
                if video.parent.resolve() != destination.resolve():
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(video.parent, destination)
                return True
            except (OSError, ValueError, TypeError):
                continue
        return False
