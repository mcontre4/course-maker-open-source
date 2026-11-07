"""Immutable approved inputs and canonical Remotion timeline; no platform rendering."""

import hashlib
import io
import json
import math
import re
import shutil
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.courses.application.generate_storyboard import artifact_hash
from app.courses.ports.animator import AnimationInput, AnimationUnavailable

PROMPT_VERSION = "animator-rive-visual-production-v1"


def reject_symlinks(root: Path) -> None:
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob("*")):
        raise AnimationUnavailable("Symlinks are forbidden in animation workspaces")


def preflight(request: AnimationInput) -> None:
    request.storyboard.validate_plan(request.plan, request.storyboard.target_video_minutes)
    request.alignment.validate_storyboard(request.storyboard)
    if request.alignment.storyboard_hash != artifact_hash(asdict(request.storyboard)):
        raise AnimationUnavailable(
            "Stale alignment: regenerate speech from the approved storyboard"
        )
    if not request.visual_style.strip() or len(request.visual_style) > 4000:
        raise AnimationUnavailable("A visual style specification is required")
    if request.alignment.duration_sec > 3600 or len(request.audio) != len(request.alignment.scenes):
        raise AnimationUnavailable("Incomplete audio or lesson exceeds the one-hour limit")
    for scene, audio in zip(request.alignment.scenes, request.audio, strict=True):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", scene.scene_id):
            raise AnimationUnavailable("Scene IDs must be safe HTML and file identifiers")
        if hashlib.sha256(audio).hexdigest() != scene.audio_sha256:
            raise AnimationUnavailable("Aligned audio checksum mismatch")
        try:
            with wave.open(io.BytesIO(audio)) as wav:
                if (
                    wav.getnchannels() != 1
                    or wav.getsampwidth() != 2
                    or wav.getframerate() != request.alignment.settings.sample_rate
                    or not math.isclose(
                        wav.getnframes() / wav.getframerate(), scene.duration_sec, abs_tol=0.001
                    )
                ):
                    raise AnimationUnavailable("Audio format or measured duration mismatch")
        except (wave.Error, EOFError) as exc:
            raise AnimationUnavailable("Invalid narration WAV") from exc


def frame(seconds: float) -> int:
    """Nearest frame, ties forward; identical to Math.round for nonnegative times."""
    return math.floor(seconds * 30 + 0.5)


def timing_manifest(request: AnimationInput) -> dict[str, Any]:
    scenes = []
    for index, scene in enumerate(request.alignment.scenes):
        start = frame(scene.timeline_start_sec)
        end = math.ceil((scene.timeline_start_sec + scene.duration_sec) * 30)
        scenes.append(
            {
                "scene_id": scene.scene_id,
                "start_sec": scene.timeline_start_sec,
                "duration_sec": scene.duration_sec,
                "start_frame": start,
                "duration_frames": end - start,
                "visual_duration_frames": (
                    frame(request.alignment.scenes[index + 1].timeline_start_sec)
                    if index + 1 < len(request.alignment.scenes)
                    else math.ceil(request.alignment.duration_sec * 30)
                )
                - start,
                "audio": f"audio/{scene.scene_id}.wav",
                "cues": [
                    {
                        "cue_id": cue.id,
                        "start_sec": cue.start_sec,
                        "end_sec": cue.end_sec,
                        "start_frame": frame(cue.start_sec),
                        "end_frame": frame(cue.end_sec),
                        "absolute_start_frame": start + frame(cue.start_sec),
                    }
                    for cue in scene.cues
                ],
            }
        )
    return {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "duration_sec": request.alignment.duration_sec,
        "duration_frames": math.ceil(request.alignment.duration_sec * 30),
        "scenes": scenes,
    }


def stage(request: AnimationInput, job: Path, tools: Path) -> dict[str, bytes]:
    reject_symlinks(job)
    inputs, project = job / "inputs", job / "remotion"
    inputs.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        tools / "template",
        project,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("node_modules"),
    )
    (project / "public/audio").mkdir(parents=True, exist_ok=True)
    (project / "src/scenes").mkdir(parents=True, exist_ok=True)
    for name, value in {
        "course-guide.json": asdict(request.guide),
        "lesson-plan.json": asdict(request.plan),
        "storyboard.json": asdict(request.storyboard),
        "alignment.json": asdict(request.alignment),
        "visual-style.json": {"specification": request.visual_style},
    }.items():
        (inputs / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))
    manifest = timing_manifest(request)
    (job / "hyperframes.json").write_text(json.dumps(manifest, indent=2))
    (project / "src/timeline.json").write_text(json.dumps(manifest, indent=2))
    imports, hosts = [], []
    for index, (scene, audio) in enumerate(
        zip(request.alignment.scenes, request.audio, strict=True)
    ):
        name = scene.scene_id
        (project / f"public/audio/{name}.wav").write_bytes(audio)
        imports.append(f"import Scene{index} from './scenes/{name}';")
        hosts.append(
            f"<Sequence from={{timeline.scenes[{index}].start_frame}} "
            f"durationInFrames={{timeline.scenes[{index}].visual_duration_frames}}>"
            f"<HoldScene component={{Scene{index}}} "
            f"frames={{timeline.scenes[{index}].duration_frames}}/></Sequence>"
            f"<Sequence from={{timeline.scenes[{index}].start_frame}} "
            f"durationInFrames={{timeline.scenes[{index}].duration_frames}}>"
            f"<Audio src={{staticFile(timeline.scenes[{index}].audio)}}/></Sequence>"
        )
    wasm = project / "public/skia/canvaskit.wasm"
    wasm.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tools / "node_modules/canvaskit-wasm/bin/full/canvaskit.wasm", wasm)
    rive_wasm = project / "public/rive/rive.wasm"
    rive_wasm.parent.mkdir(parents=True, exist_ok=True)
    rive_resource = tools / "node_modules/@rive-app/canvas-advanced/rive.wasm"
    if rive_resource.exists():
        shutil.copyfile(rive_resource, rive_wasm)
    # Explicit local font assets keep generation, QA and playback typography identical.
    font_dir = tools / "node_modules/@fontsource/inter/files"
    for font in font_dir.glob("inter-latin-*-normal.woff2"):
        destination = project / "public/fonts" / font.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(font, destination)
    (project / "src/Root.tsx").write_text(
        "import React, {ComponentType} from 'react';\n"
        "import {AbsoluteFill, Audio, Composition, Freeze, Sequence, staticFile, "
        "useCurrentFrame} from 'remotion';\n"
        "import timeline from './timeline.json';\n"
        + "\n".join(imports)
        + "\nconst HoldScene = ({component: Scene, frames}: "
        "{component: ComponentType; frames: number}) "
        "=> <Freeze frame={Math.min(useCurrentFrame(), frames - 1)}><Scene/></Freeze>;\n"
        "const Course = () => <AbsoluteFill style={{background: '#101827'}}>"
        + "".join(hosts)
        + '</AbsoluteFill>;\nexport const Root = () => <Composition id="Course" '
        "component={Course} width={1920} height={1080} fps={30} "
        "durationInFrames={timeline.duration_frames}/>;\n"
    )
    owned = [
        *inputs.glob("*.json"),
        job / "hyperframes.json",
        project / "src/index.ts",
        project / "src/Root.tsx",
        project / "src/timeline.json",
        project / "src/remotion-env.d.ts",
        project / "src/toolkit.css",
        project / "types/skia-web.d.ts",
        project / "src/visuals/ApprovedEquation.tsx",
        project / "src/visuals/RiveIllustration.tsx",
        project / "remotion.config.ts",
        wasm,
        *([rive_wasm] if rive_wasm.exists() else []),
        *(project / "public/fonts").glob("*.woff2"),
        *(project / "vendor").rglob("*.*"),
        *(project / "public/audio").glob("*.wav"),
        *(
            project / name
            for name in ("package.json", "package-lock.json", "tsconfig.json", "CONTRACT.md")
        ),
    ]
    return {str(p.relative_to(job)): p.read_bytes() for p in owned}


def validate_files(request: AnimationInput, job: Path, protected: dict[str, bytes]) -> None:
    reject_symlinks(job)
    for name, content in protected.items():
        path = job / name
        if not path.is_file() or path.read_bytes() != content:
            raise AnimationUnavailable(
                "Animation author modified an approved input, audio or timeline scaffold"
            )
    project = job / "remotion"
    files = list(project.rglob("*"))
    if len(files) > 500 or sum(p.stat().st_size for p in files if p.is_file()) > 250_000_000:
        raise AnimationUnavailable("Animation project exceeds file or size budget")
    for path in files:
        if path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
            raise AnimationUnavailable("The animator produces editable source, not rendered videos")
        if path.suffix.lower() == ".html" or path.name == "node_modules":
            raise AnimationUnavailable(
                "Generate Remotion source only, without HTML or node_modules"
            )
    path = project / "scene-manifest.json"
    try:
        manifest = json.loads(path.read_text())
        canonical = timing_manifest(request)
        if {k: manifest[k] for k in canonical if k != "scenes"} != {
            k: v for k, v in canonical.items() if k != "scenes"
        } or len(manifest["scenes"]) != len(canonical["scenes"]):
            raise ValueError("Composition timing mismatch")
        for expected, actual in zip(canonical["scenes"], manifest["scenes"], strict=True):
            if {k: actual[k] for k in expected if k != "cues"} != {
                k: v for k, v in expected.items() if k != "cues"
            } or len(actual["cues"]) != len(expected["cues"]):
                raise ValueError("Scene timing mismatch")
            source = project / f"src/scenes/{expected['scene_id']}.tsx"
            if not source.is_file():
                raise ValueError("Animation author did not implement every scene")
            for cue, event in zip(expected["cues"], actual["cues"], strict=True):
                if {k: event[k] for k in cue} != cue:
                    raise ValueError("Cue timing mismatch")
                if not all(
                    isinstance(event.get(k), str) and event[k].strip()
                    for k in ("visual_event", "target")
                ):
                    raise ValueError("Every cue needs a meaningful visible event and target")
        if not (project / "IMPLEMENTATION.md").read_text().strip():
            raise ValueError("Missing implementation summary")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AnimationUnavailable(f"Invalid scene/cue manifest: {exc}") from exc


def project_digest(project: Path) -> str:
    return artifact_hash(
        {
            str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(project.rglob("*"))
            if p.is_file()
        }
    )
