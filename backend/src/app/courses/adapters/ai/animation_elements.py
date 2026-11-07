"""One visual element agent identifies artwork and generates up to ten items at once."""

import fcntl
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import asdict, replace
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.courses.adapters.ai.direct_animation import DirectAnimationCall, unfence
from app.courses.application.generate_storyboard import artifact_hash
from app.courses.ports.animation_elements import AnimationElementSpec, PreparedAnimationElement
from app.courses.ports.animator import AnimationInput, AnimationUnavailable


class _Element(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,59}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    format: Literal["canvas", "svg"]
    scene_ids: tuple[str, ...] = Field(min_length=1, max_length=100)


class _Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    elements: tuple[_Element, ...] = Field(max_length=24)


class StoryboardElementAgent:
    def __init__(self, root: Path, tools: Path, llm: DirectAnimationCall) -> None:
        self._root, self._tools, self._llm = root, tools, llm

    def _complete(
        self,
        request: AnimationInput,
        payload: dict[str, object],
        stage: str,
        validate: Callable[[str], None],
    ) -> str:
        try:
            return self._cached_complete(request, payload, stage, validate)
        except OSError as exc:
            raise AnimationUnavailable(
                "Visual element preparation could not read or save its files"
            ) from exc

    def _cached_complete(
        self,
        request: AnimationInput,
        payload: dict[str, object],
        stage: str,
        validate: Callable[[str], None],
    ) -> str:
        prompt = Path(__file__).with_name("visual_element_prompt.md").read_text()
        style = self._tools / "styles" / request.visual_style_id
        context = {
            "storyboard": asdict(request.storyboard),
            "visual_style": request.visual_style,
            "style": {name: (style / name).read_text() for name in ("STYLE.md", "drawing.js")},
            **payload,
        }
        scope = replace(request.session, session_id=None) if request.session else None
        digest = artifact_hash(
            {
                "context": context,
                "prompt": prompt,
                "model": self._llm.model,
                "effort": self._llm.effort,
                "adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "scope": asdict(scope) if scope else None,
                "regeneration_key": request.regeneration_key,
            }
        )
        job = self._root / ".elements" / digest
        job.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (job / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            saved = job / "result.json"
            if saved.is_file():
                try:
                    if saved.stat().st_size > 1000000:
                        raise ValueError("Oversized element cache")
                    cached = json.loads(saved.read_text())
                    output = cached["output"]
                    if (
                        not isinstance(output, str)
                        or hashlib.sha256(output.encode()).hexdigest() != cached["sha256"]
                    ):
                        raise ValueError("Element cache checksum mismatch")
                    validate(output)
                    return output
                except (ValueError, KeyError, TypeError, AnimationUnavailable):
                    # A corrupt cache must not permanently poison subsequent attempts.
                    saved.unlink()
            result = self._llm.complete_with_session(
                prompt,
                [{"type": "text", "text": json.dumps(context, ensure_ascii=False)}],
                stage,
                scope,
            )
            output = unfence(result.output)
            validate(output)
            (job / "request.json").write_text(json.dumps(context, ensure_ascii=False, indent=2))
            (job / "session.json").write_text(json.dumps({"session_id": result.session_id}))
            # Publish atomically: a killed process must not leave a truncated cache entry.
            pending = job / "result.tmp"
            pending.write_text(
                json.dumps(
                    {
                        "output": output,
                        "sha256": hashlib.sha256(output.encode()).hexdigest(),
                    }
                )
            )
            pending.replace(saved)
            return output

    def _identify(self, request: AnimationInput) -> tuple[AnimationElementSpec, ...]:
        def validate(output: str) -> None:
            plan = _Plan.model_validate_json(output)
            ids = [element.id for element in plan.elements]
            scenes = {scene.scene_id for scene in request.storyboard.scenes}
            if len(set(ids)) != len(ids) or any(
                not set(element.scene_ids) <= scenes for element in plan.elements
            ):
                raise ValueError("Duplicate element IDs or unknown scenes")

        try:
            output = self._complete(request, {"task": "identify"}, "element_planning", validate)
            plan = _Plan.model_validate_json(output)
            return tuple(AnimationElementSpec(**element.model_dump()) for element in plan.elements)
        except ValueError as exc:
            raise AnimationUnavailable(
                "Visual element agent returned an invalid element list"
            ) from exc

    def generate(self, request: AnimationInput) -> tuple[PreparedAnimationElement, ...]:
        specs = self._identify(request)
        if not specs:
            return ()
        with ThreadPoolExecutor(max_workers=min(10, len(specs))) as executor:
            # ContextVars contain usage/cancellation scope. Each worker needs its own copy.
            futures = [
                executor.submit(copy_context().run, self._generate_one, request, spec, specs)
                for spec in specs
            ]
            return tuple(future.result() for future in futures)

    def _generate_one(
        self,
        request: AnimationInput,
        spec: AnimationElementSpec,
        specs: tuple[AnimationElementSpec, ...],
    ) -> PreparedAnimationElement:
        source = self._complete(
            request,
            {
                "task": "generate",
                "assigned_element": asdict(spec),
                "element_plan": [asdict(s) for s in specs],
            },
            "element_generation",
            lambda source: self._validate_source(spec, source),
        )
        return PreparedAnimationElement(spec, source)

    def _validate_source(self, spec: AnimationElementSpec, source: str) -> None:
        if not source.strip() or len(source.encode()) > 60000:
            raise AnimationUnavailable(f"Missing or oversized element: {spec.id}")
        if spec.format == "canvas":
            if not re.search(r"\bfunction\s+draw_" + re.escape(spec.id) + r"\s*\(", source):
                raise AnimationUnavailable(f"Element {spec.id} is missing its drawing function")
            # Snippets remain editable input data. The assembled animation is checked
            # by the existing offline worker; the API image does not require Node.
        else:
            try:
                root = ET.fromstring(source)
                if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
                    raise ValueError("Expected SVG root")
            except (ET.ParseError, ValueError) as exc:
                raise AnimationUnavailable(f"Element {spec.id} contains invalid SVG") from exc
