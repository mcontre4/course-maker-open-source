# Tech Glow Explainer · v1

Family: Popular Explainer Looks. `source-prompt.txt` preserves the full supplied
prompt and `examples/reference-ai.js` preserves the executable reference unchanged.
H and SOUND are bundled unchanged. The reference explains AI learning; adapt its
medium to the approved lesson rather than copying its subject or statistics.

Use deep navy-to-indigo space, drifting electric glows, a perspective floor grid,
gradient-stroked icon tiles, thin neon borders, gradient headlines and counters,
and node diagrams with racing light pulses. Use Space Grotesk for headlines and
numbers and Inter for labels. Both families are bundled locally.

`TG` exposes the original background, glowDot, ring, card, tile, pill, gtext,
revealLine, eyebrow, bez, seg2, ptAt, sub, pulseOn and connector helpers; C and
GRAD_HEAD/GRAD_NUM contain the palette. ICONS contains reference line icons;
create accurate topic-specific paths where those icons do not fit. Use smooth
eased builds, icon draw-ons, gentle overshoot, continuous camera pushes/pans,
light-speed streaks for meaningful scale changes, and gradient count-ups.

The player applies STYLE.finish once after every frame. This runs the reference's
unchanged two-radius bloom at amount 1 (additive alpha .45/.5) followed by the
original .45 vignette in color 2,3,16. Do not call bloom or finish again in explainer.
Retain the original background glows, perspective grid and drifting particles.
Every frame must be a pure function of time; H.rng seeds all randomness.

Keep headlines >=44px, necessary labels >=28px and key numbers >=64px at 1280×720,
including overriding small default label sizes in the reference helpers. Make
objects and connectors explain the content rather than making a deck of cards.
Study explainerSound for glass tones, filtered glides, ticks and resolving hits.
Use the same event constants for motion and effects, with effects below narration
and no more than about three simultaneous sounds.

The source prompt's standalone HTML/storyboard approval workflow is reference
material. The platform's approved lesson, measured narration timeline, visualPlan
and review setting govern production. Author only animation.js, reuse the trusted
player, and preserve measured narration rather than enforcing the example length.
