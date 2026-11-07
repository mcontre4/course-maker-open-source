# Whiteboard Explainer · v1

Family: Hand-Drawn. The full uploaded prompt is preserved in source-prompt.txt;
examples/reference-ai.js is the complete original executable reference. H and
SOUND are unchanged. Adapt the medium to the approved lesson; do not transplant
the reference's AI topic, example objects or statistics unless they fit.

Use streaky chisel-tip dry-erase marker with pooled edges, pale wet centers,
felt-tip skips, wobbly double-traced boxes/arrows and jittered marker lettering.
Use black #1d1f26 ink with blue #1f4fc2, red #d4262f and green #16884a accents.
Permanent Marker (400) supplies headlines/numbers; Kalam (700) supplies labels.
Both fonts are bundled locally. Keep headlines >=44px, required labels >=28px
and key numbers >=64px at 1280×720, including corner annotations.

WB exposes the original seg, normals, wobble, ell, bez, tracePath, marker and
mText helpers. Use marker(ctx, points, color, width, seed, progress) for strokes
and mText(ctx, text, x, y, fontSpec, color, seed, progress, rotation) for lettering.
WB.background paints the reference board gradient and cleaner residue; ghostBoard
provides its cached erased background in world coordinates. The original example
contains felt-eraser wipe masks, FIBRES and haze recipes to reuse for transitions.
Draw accurate topic-specific diagrams rather than arbitrary boxes or doodles.

The player resets the marker tip with STYLE.beginFrame before every draw, so
seeking does not retain the previous frame's drawing state. WB.tip() returns the
current in-progress stroke/lettering tip for drawing the marker tool. All geometry,
reveal progress and camera motion must be computed from t with seeded randomness.
The player runs STYLE.finish once: the reference's drifting gloss, ceiling-light
reflections, lower-board falloff and grain at .018 strength. Do not apply gloss or
grain a second time. Keep pooled ink, dry streaks and eraser ghosts in the drawing.

Draw strokes sequentially as if a hand were drawing live. Follow the marker across
one big board with a continuous camera; wipe with a felt eraser leaving streaky
residue when the story needs fresh space. Counters are re-scrawled in marker.
Use the reference score's marker squeaks, writing, felt erasure, cap clicks and
resolving effects; synchronize them to visual events beneath the narration.

The standalone HTML/storyboard approval instructions describe reference usage.
Production follows the platform's approved lesson, measured narration timeline,
visualPlan and saved review setting. Author only animation.js, reuse the existing
player and preserve narration timing rather than imposing the example duration.
