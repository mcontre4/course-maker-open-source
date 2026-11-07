"""Select the trusted style card and curated executable example for a visual job."""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.courses.domain.visual_style import VisualStyle
from app.courses.ports.storyboard_agent import StoryboardGenerationUnavailable


def storyboard_style_reference(
    tools: Path, style_id: str, version: int, script: dict[str, Any] | None = None
) -> str:
    selected = VisualStyle(style_id, version)
    try:
        card = (tools / "styles" / selected.id / "STYLE.md").read_text()
    except OSError as exc:
        raise StoryboardGenerationUnavailable(
            f"The selected visual style reference is unavailable: {selected.id} v{selected.version}"
        ) from exc
    reference = (
        f"Selected visual style: {selected.id}, version {selected.version}.\n"
        "Use this shared reference for visual direction; adapt its medium and choreography "
        "to the lesson rather than copying its subject matter.\n" + card
    )
    try:
        # Validate the catalog during the preflight before scripting incurs cost.
        example = select_teaching_example(tools, style_id, script or {})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StoryboardGenerationUnavailable(
            f"The selected teaching reference is unavailable: {selected.id} v{selected.version}"
        ) from exc
    if script is not None and example is not None:
        reference += "\nSelected teaching example (adapt, do not copy facts):\n" + example.notes
    return reference


@dataclass(frozen=True)
class TeachingExample:
    id: str
    source: Path
    image: Path
    notes: str


def teaching_example_identity(tools: Path) -> str:
    """Reference edits invalidate authored-source caches, including reference pixels."""
    root = tools / "teaching-examples"
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _example_file(root: Path, name: str, suffix: str, limit: int) -> Path:
    relative = PurePosixPath(name)
    path = root / relative
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix != suffix
        or not path.resolve().is_relative_to(root.resolve())
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > limit
    ):
        raise ValueError(f"Invalid teaching example resource: {name}")
    return path


def select_teaching_example(
    tools: Path, style_id: str, lesson: dict[str, Any]
) -> TeachingExample | None:
    """Match explanatory structure in frozen speech, identically before/after storyboarding.

    The catalog is optional for older/custom tool packages. Manifest order breaks ties;
    unknown language/material falls back to its declared default, without another LLM call.
    """
    root = tools / "teaching-examples"
    manifest = root / "manifest.json"
    if not manifest.is_file():
        return None
    catalog = json.loads(manifest.read_text())
    scenes = lesson.get("segments", lesson.get("scenes", []))
    speech = " ".join(
        str(scene.get("learning_purpose", "")) + " " + str(scene.get("narration_text", ""))
        for scene in scenes
    )
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", speech.casefold())
        if not unicodedata.combining(char)
    )
    candidates = []
    for entry in catalog["examples"]:
        source = _example_file(root, entry["source"], ".js", 60000)
        image = _example_file(root, entry["image"], ".png", 2000000)
        notes = _example_file(root, entry["notes"], ".json", 8000).read_text()
        if style_id not in entry["styles"] and "*" not in entry["styles"]:
            continue
        score = sum(
            bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", normalized))
            for term in entry["terms"]
        )
        if entry["id"] == "worked-example" and any(s.get("equations") for s in scenes):
            score += 20
        candidates.append(
            (
                score,
                int(style_id in entry["styles"]),
                int(entry["id"] == catalog["default"]),
                TeachingExample(entry["id"], source, image, notes),
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[:3])[3]


def preferred_style_example(style: Path) -> Path | None:
    manifest = style / "manifest.json"
    if not manifest.is_file():
        return next(iter(sorted((style / "examples").glob("*.js"))), None)
    data = json.loads(manifest.read_text())
    examples = data.get("examples", []) if isinstance(data, dict) else None
    if not isinstance(examples, list) or any(not isinstance(p, str) for p in examples):
        raise ValueError("Style manifest examples must be an ordered list of paths")
    if not examples:
        return None
    preferred = PurePosixPath(examples[0])
    path = style / preferred
    if (
        preferred.is_absolute()
        or ".." in preferred.parts
        or preferred.suffix != ".js"
        or not path.resolve().is_relative_to(style.resolve())
        or not path.is_file()
    ):
        raise ValueError(
            "The preferred style example must be an existing JavaScript file in its package"
        )
    return path
