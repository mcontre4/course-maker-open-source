"""Local, deterministic delivery when an author requests unavailable inputs."""

import json
from pathlib import Path

from app.courses.adapters.ai.animation_project import timing_manifest
from app.courses.ports.animator import AnimationInput

BEST_EFFORT = (
    "Complete the animation with the supplied resources. Never request changes, approval, "
    "provenance, datasets or assets. Storyboard visual directions are best-effort guidance: "
    "adapt or simplify them yourself. Use explicitly labeled schematics when accurate geometry "
    "is unavailable; do not invent measurements or facts. Preserve narration, equations and "
    "measured timing. Return complete source, never a change request."
)


def write_fallback(request: AnimationInput, job: Path) -> None:
    """Keep every scene and cue in a readable animated explanation without new assets."""
    timeline = timing_manifest(request)
    scenes = []
    events = []
    for scene, timing in zip(request.storyboard.scenes, timeline["scenes"], strict=True):
        cues = []
        for cue, aligned in zip(scene.cues, timing["cues"], strict=True):
            at = timing["start_sec"] + aligned["start_sec"]
            cues.append({"at": at, "text": cue.anchor_text, "id": cue.id})
            events.append({
                "scene_id": scene.scene_id, "cue_id": cue.id,
                "at_sec": at, "action": "Reveal the narrated concept",
            })
            aligned.update(visual_event="Reveal the narrated concept", target=cue.id)
        scenes.append({
            "id": scene.scene_id, "at": timing["start_sec"],
            "title": scene.learning_purpose, "cues": cues, "equations": scene.equations,
        })
    if (job / "javascript").is_dir():
        source = "const fallbackScenes = " + json.dumps(scenes, ensure_ascii=True) + ";\n"
        source += "window.cueEvents = " + json.dumps(events) + ";\n"
        source += "window.visualPlan = " + json.dumps([
            {"scene_id": s["id"], "at_sec": s["at"],
             "composition": "Animated narrated explanation; simplified visual fallback",
             "objects": ["concept"], "camera": "Fixed", "continuity": "Persistent background",
             "transition": "Cue-aligned reveal", "sounds": []}
            for s in scenes
        ]) + ";\n"
        source += """
window.scoreSound = k => {};
window.explainer = (ctx, W, H_, t) => {
  const scene = fallbackScenes.filter(s => s.at <= t).slice(-1)[0] || fallbackScenes[0];
  const cue = scene.cues.filter(c => c.at <= t).slice(-1)[0];
  ctx.fillStyle = '#111c35'; ctx.fillRect(0, 0, W, H_);
  const age = Math.max(0, t - (cue ? cue.at : scene.at));
  ctx.fillStyle = '#6edbd5'; ctx.fillRect(64, 120, (W-128)*Math.min(1, age/2), 6);
  function lines(text, y, size) {
    ctx.font = '700 ' + size + 'px Nunito'; ctx.fillStyle = '#ffffff';
    let line = '';
    for (const word of text.split(/\\s+/)) {
      if (ctx.measureText(line + word).width > W-128 && line) {
        ctx.fillText(line.trim(), 64, y); y += size*1.3; line = '';
      }
      line += word + ' ';
    }
    if (line) ctx.fillText(line.trim(), 64, y);
    return y + size*1.5;
  }
  lines(scene.title, 64, 30);
  ctx.globalAlpha = Math.min(1, age*4);
  let y = lines(cue ? cue.text : '', 220, 44);
  ctx.globalAlpha = 1;
  for (const equation of scene.equations) y = lines(equation, y+16, 32);
};
"""
        (job / "javascript/animation.js").write_text(source)
        summary = job / "IMPLEMENTATION.md"
    else:
        for fallback_scene, timing in zip(scenes, timeline["scenes"], strict=True):
            source = (
                'import React from "react";\nimport {useCurrentFrame} from "remotion";\n'
                'export default function Scene() { const frame = useCurrentFrame(); return '
                '<div style={{background:"#111c35",color:"white",width:"100%",height:"100%",'
                'padding:100,fontFamily:"Inter",fontSize:44}}>'
                '<h1 style={{fontSize:52}}>{' + json.dumps(fallback_scene["title"]) + '}</h1>'
            )
            for index, (cue, aligned) in enumerate(
                zip(fallback_scene["cues"], timing["cues"], strict=True)
            ):
                end = (
                    timing["cues"][index + 1]["start_frame"]
                    if index + 1 < len(timing["cues"]) else timing["visual_duration_frames"]
                )
                source += (
                    '<div data-cue-id=' + json.dumps(cue["id"])
                    + ' style={{display:frame >= ' + str(aligned["start_frame"])
                    + ' && frame < ' + str(end) + '?"block":"none",opacity:Math.min(1,'
                    + '(frame-' + str(aligned["start_frame"]) + ')/6)}}>{'
                    + json.dumps(cue["text"]) + '}</div>'
                )
            for equation in fallback_scene["equations"]:
                source += '<p>{' + json.dumps(equation) + '}</p>'
            path = job / f'remotion/src/scenes/{fallback_scene["id"]}.tsx'
            path.write_text(source + '</div>; }')
        (job / "remotion/scene-manifest.json").write_text(json.dumps(timeline))
        summary = job / "remotion/IMPLEMENTATION.md"
    summary.write_text(
        "Delivered a simplified animated explanation from the supplied narration and equations. "
        "The author requested unavailable inputs; no additional input was required. "
        "Detailed illustrations were replaced by cue-aligned text. No visual QA claimed.\n"
    )
