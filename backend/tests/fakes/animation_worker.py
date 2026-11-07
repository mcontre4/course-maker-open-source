import json

from app.courses.ports.animator import AnimationUnavailable


def write_animation_source(request, job):
    """Tiny source fixture; real renderer/TypeScript checks live in the tool tests."""
    manifest = json.loads((job / "remotion/src/timeline.json").read_text())
    for scene, aligned in zip(request.storyboard.scenes, manifest["scenes"], strict=True):
        content = 'import React from "react";\nexport default () => <div>'
        for equation in scene.equations:
            content += "{" + json.dumps(equation) + "}"
        for cue in aligned["cues"]:
            cue.update(visual_event="Reveal concept", target=cue["cue_id"])
            content += f'<div data-cue-id="{cue["cue_id"]}">Concept</div>'
        (job / f"remotion/src/scenes/{scene.scene_id}.tsx").write_text(content + "</div>;")
    (job / "remotion/scene-manifest.json").write_text(json.dumps(manifest))
    (job / "remotion/IMPLEMENTATION.md").write_text("Test fixture. No visual QA performed.")


class RecordingAnimationCommands:
    """Fake external commands; input staging and validation use the real filesystem."""

    def __init__(self, request):
        self.request = request
        self.calls = []
        self.invalid_outputs = 0
        self.change_request = None
        self.omit_source = False
        self.forge_result = False

    def __call__(self, job, kind, args, prompt, name):
        self.calls.append((kind, args, prompt, name))
        if kind == "codex":
            if not self.omit_source:
                write_animation_source(self.request, job)
            if self.forge_result:
                (job / "result.json").write_text('{"forged":true}')
            if self.change_request is not None:
                (job / "change-request.json").write_text(json.dumps(self.change_request))
        if kind == "validate" and self.invalid_outputs:
            self.invalid_outputs -= 1
            raise AnimationUnavailable("nondeterministic code rejected by static validator")
