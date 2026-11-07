# Watercolor Wash · v1

Family: Painterly. The supplied prompt is preserved in `source-prompt.txt`; the
complete executable reference is `examples/reference-ai.js`. H and SOUND are
bundled unchanged. The example explains AI learning; reuse its medium and
techniques with original subjects appropriate to the approved lesson.

Use transparent pigment glazed in dozens of ragged low-opacity layers on
cold-press paper, dark pooled edges, wet-in-wet bleeds, cauliflower blooms,
granulation and untouched white paper highlights over a faint pencil sketch.
Use Caveat brush lettering (400/700), round-brush arrows with pooled edges,
rewritten counters and red alizarin circles for emphasis. Washes flood from their
pencil outlines; edges darken as water dries and blooms creep outward.

`WC` exposes the reference's P, deform, poly, circlePts, grid, makeMottle, rimPool,
exWash, blob and exBloom helpers. Apply rimPool to wash layers, retain mottling and
bloom recipes from the example, and composite them onto warm paper [251,248,240].
The player runs `STYLE.finish` once on every frame: the original cold-press tooth
and pigment granulation pass at full strength. Do not run that pass twice. Static
texture/layer caches are fine; frame state and randomness must be seeded.

Use one long sketchbook sheet with continuous camera pans when ideas connect.
For actual scene changes, use paper travel or flooding washes from the reference.
Keep headlines >=44px, necessary labels >=28px and key numbers >=64px at 1280×720.
Brush lettering and illustrations must remain legible on phones.

Study the reference explainerSound for brush/water/paper effects; synchronize
effects to visible events, with at most about three simultaneous effects. The
platform supplies narration: keep effects underneath it and use voiceover mode.

The original prompt describes a standalone, silent-narrator storyboard approval
workflow and 12–30 second example. In this software the approved lesson, measured
narration timeline, visualPlan and platform review setting govern production.
Author animation.js using the existing player, local fonts and trusted runtime;
do not add another player, request approval or shorten the supplied narration.
