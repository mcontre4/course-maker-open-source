# Gouache Travel Poster · v1

Family: Painterly. source-prompt.txt preserves the uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are unchanged. Invent accurate lesson subjects rather than carrying over the
power station, AI machine, pets or illustrative statistics.

Six opaque matte colours: navy #1e3442, teal #2f7f83, orange #e0612b,
mustard #f2b440, cream #f3e7cc and rose #eaa58a. Use receding flat layers,
dry-brush edges, chalky pigment, board grain and bold poster lettering. Bebas Neue
400 and Oswald 400/700 are bundled locally. Headlines >=44px, necessary labels
>=28px and key numbers >=64px at 1280×720; override smaller reference defaults.

GP.frame(W,H_) creates a fresh cream buffer and returns {buf, paint, commit}.
paint(col, [x0,y0,x1,y1], drawMask, options) runs the unchanged reference painter:
col is an RGB array (see GP.PAL); drawMask(c) draws white shapes/text into a mask;
options include edge, rag, dir ('h', 'v', 'd'), tex, p (sweep progress 0..1) and key.
Set all geometry and transforms inside drawMask; pixel-buffer drawing does not
inherit the destination canvas's camera. Paint in back-to-front order. Bounds must
enclose the entire mask. Avoid gradients/transparency as substitutes for opaque
paint. commit(ctx) writes the painted buffer. The player then runs STYLE.finish
once, applying the original matte board grain at full strength. Do not add it twice.

GP.gpCache stores deterministic fields by dimensions. A paint key caches a finished
static mask/colour; use unique keys for each distinct subject/state, and omit key
for moving or changing masks. Never reuse a key with different geometry or colour.
GP.makePainter exposes the lower-level reference API for custom buffers.

Move layers in parallax like stacked painted cut-outs. Change scenes with a fresh
cream coat swept across the board, then repaint the next poster colour by colour.
Use flat poster-shaped arrows, numbers repainted in a dark lettering band and orange
starbursts at key moments. Keep related elements continuous when the story builds.
Study the reference score for brush sweeps, paint dabs, stamps and warm resolving
hits; align those events to the measured narration.

The uploaded standalone HTML/storyboard instructions describe the reference.
The platform's approved lesson, measured narration, visualPlan, cueEvents and saved
review preference govern jobs. Author only animation.js with the trusted player;
do not impose the example's topic, short duration or standalone approval workflow.
