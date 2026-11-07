# Optional parallel visual elements

In a standalone or course lesson studio, open **Quality & speed → Technical
settings → Pre-generate visual elements**. It is off for new lessons and applies
to the next generation. Reopening saved source restores its recorded choice so
delivery retries do not unexpectedly switch paths. The animation/video/automatic HTTP requests accept the
strict boolean `prepareElements` (or `prepare_elements`).

When enabled, `ProduceCanvasAnimation` calls one injected `AnimationElementAgent`.
Its `StoryboardElementAgent` implementation owns the complete step: it identifies
whole subjects, props and useful grouped artwork, then generates them with up to
**ten concurrent LLM calls**. It deduplicates recurring objects, records scene IDs,
avoids body parts and limits the inventory to 24 elements. Every call receives the
selected style; artwork calls also receive the shared element plan and storyboard.
The results are self-contained Canvas drawing functions or SVG.

The single agent uses one instruction set, the `visual_elements` conversation role
and the selected animator model with low reasoning effort. Identification and
generation remain separate usage phases (`element_planning`, `element_generation`)
in the spending and progress UI. Threads copy the caller's usage/cancellation
context and have independent conversations under the same agent identity, so
parallel calls do not contend over one conversation revision.

The animator receives the list and editable sources in `inputs.json`. It copies,
adapts or replaces artwork inside its final `animation.js`, retaining control of
layout, visual cohesion, motion, sound and timing. Snippets are data, not runtime
globals. The existing offline worker validates the complete animation; the API
does not need a local Node installation. Review/repair uses the same prepared
sources without another planning or generation pass.

Private `.elements` artifacts cache the plan and individual successful outputs
by storyboard, style bytes, model, prompts, agent implementation, operation scope
and regeneration key. Invalid outputs are not cached; cached output checksums are
verified and corrupt entries are regenerated. An interrupted run can reuse
successful work. Saved animation metadata records `prepare_elements`, so
switching the toggle cannot reuse a source produced with the opposite setting.
The flag does not change the saved storyboard or narration.

## Initial live check, before the single-agent consolidation

On November 3, 2026, the saved 56.64-second Halloween history storyboard ran with
Sonnet and the new flag enabled. It identified 10 elements, including a whole
costumed child with bag, grouped visitors and a house doorway. Calls ran eight at
a time. Planning took 10.95 seconds, element generation 17.22 seconds of elapsed
time (94.41 seconds summed across calls), and animator authoring 22.65 seconds.
The completed run took 151.18 seconds including offline rendering and delivery.
Source checks, deterministic seek checks and full video validation passed.
AI visual review was disabled for this experiment.

The animator substantially adapted the supplied artwork. This establishes the
parallel handoff and a technically valid delivery; it does not establish a total
latency or visual-quality improvement over the bypass path. No baseline run was
made. Private evidence and video are under `backend/.artifacts/element-smoke/`.

Repeat with another saved job's `inputs.json` and its sibling `javascript/audio`:

```sh
poetry -C backend run python scripts/verify_animation_elements.py \
  --inputs .artifacts/animation/<saved-job>/inputs.json \
  --env-file .env --output-dir .artifacts/element-smoke-new
```

This explicitly invokes paid model calls through the configured OpenRouter
account and uses the existing offline Docker renderer. It reuses narration and
does not publish or modify the saved lesson.
