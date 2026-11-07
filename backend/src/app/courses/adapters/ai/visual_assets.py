"""Legacy asset staging for saved Remotion projects."""

import re
import shutil
from pathlib import Path

from app.courses.adapters.ai.animation_project import project_digest, reject_symlinks
from app.courses.ports.animator import AnimationInput, AnimationUnavailable


def stage_visual_assets(request: AnimationInput, job: Path, root: Path) -> dict[str, bytes]:
    if not re.fullmatch(r"\.assets/[0-9a-f]{64}/assets", request.asset_project_key):
        raise AnimationUnavailable("Invalid illustration project reference")
    source = root / request.asset_project_key
    reject_symlinks(source)
    if project_digest(source) != request.asset_output_hash:
        raise AnimationUnavailable("Generated illustration checksum mismatch")
    project = job / "remotion"
    if request.previous_project_key:
        if not re.fullmatch(r"[0-9a-f]{64}/remotion", request.previous_project_key):
            raise AnimationUnavailable("Invalid visual repair source")
        previous = root / request.previous_project_key
        reject_symlinks(previous)
        # Seed editable source, including shared drawing/layout helpers, never scaffold.
        owned = {
            "src/Root.tsx",
            "src/index.ts",
            "src/timeline.json",
            "src/remotion-env.d.ts",
            "src/toolkit.css",
            "src/visuals/ApprovedEquation.tsx",
            "src/visuals/RiveIllustration.tsx",
        }
        for old in (previous / "src").rglob("*"):
            relative = old.relative_to(previous)
            if old.is_file() and str(relative) not in owned:
                destination = project / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(old, destination)
        for name in ("scene-manifest.json", "IMPLEMENTATION.md"):
            if (previous / name).is_file():
                shutil.copyfile(previous / name, project / name)
    target = project / "public/illustrations"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return {str(p.relative_to(job)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
