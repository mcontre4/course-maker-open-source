# Risograph Zine · v1

Family: Print. source-prompt.txt preserves the full uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are unchanged. Rebuild around the approved lesson's accurate subjects; the rocket,
AI topic, pets and illustrative statistics are examples, not required content.

Use fluorescent pink #ff48b0, blue #3255a4 and yellow #ffe200, multiplied onto
stock #f2ede0. Archivo Black (400) and Space Mono (400/700) are bundled locally.
Headlines >=44px, necessary labels >=28px and key numbers >=64px at 1280×720.

RISO.plates(W,H_,t) returns three white-backed separation canvases, in yellow,
pink, blue order. Each entry has k (ink name), canvas, ctx and reveal (drum-front
y coordinate, default 1e9). Draw BLACK for ink, GREY/alpha for dotted tints, WHITE
for knockouts. The contexts already include the reference offsets (-5,+6), (+6,-3),
(0,0) and deterministic 8fps plate jitter. Apply the same scene camera to each.
RISO.composite(ctx, plates, W,H_,t) MUST run every frame: it includes the original
screen angles, halftone thresholds, mottled density, ink dropout, roller streaks,
8fps ink boil and paper grain at full strength. These passes depend on the separate
ink coverage, so they cannot be recovered from a flattened RGB image.
STYLE.finish is intentionally empty: composite already finishes the print. Never
replace the compositor with flat colour fills or add grain twice. rxStatic caches
only fields for the current dimensions; plates must be recreated/cleared per draw.

RISO.arrowQ draws quadratic flow arrows (use blue with dash arrays); T sets type;
scribbleCircle draws the pink emphasis ring. Consult the reference for two-plate
type, printed number counters and registration transitions. Carry related subjects
between beats; when a scene changes, slide the old separations away and re-register
the new ones in yellow, pink, blue drum passes, staggered by 0.11 seconds.
Use roller/paper feed sounds, registration clacks, dotted taps and press impacts
in sync with visible events, beneath narration.

The uploaded standalone HTML/storyboard instructions describe the reference.
The platform's approved lesson, measured narration, visualPlan, cueEvents and saved
review preference govern production. Author only animation.js; do not enforce the
example's topic, duration, standalone player or approval workflow on platform jobs.
