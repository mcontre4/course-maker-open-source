# International Typographic Style · v1

Family: Art & Design Movements. source-prompt.txt preserves the uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are unchanged. Use accurate lesson-specific subjects rather than carrying over the
AI topic, pet pictograms, lecture information or illustrative statistics.

A 1960s Zürich-school concert poster: strict 12-column modular grid, enormous
flush-left grotesk headlines, tight tracking, asymmetric concentric arc segments
and precise information blocks. Palette is red #e2231a, black #141414 and off-white
#f1efe9 only. Inter 400/600/800 is bundled locally. Headlines >=44px, necessary
labels >=28px and key numbers >=64px at 1280×720; override smaller hero defaults.

SWISS.grid() supplies the reference margin 48, pitch 100, columnWidth 84,
columns 12 and colX(i)=48+i*100. These logical dimensions assume 1280×720.
Align labels, charts, counters and rules to this grid. Leave deliberate negative
space; put detail in concise grid-hung blocks. Huge Inter 800 type uses tracking
around -0.045*fontSize. Study the reference's baseline-mask headline reveals.

SWISS.frame(W,H_) returns {layer,c}: draw all ink onto the transparent layer via c.
SWISS.composite(ctx,frame,W,H_) paints the off-white stock, copies the ink layer,
then runs the original noise-modulated alpha coverage, single-pixel dropouts and
70 missing-ink ring defects, faint 0.12-alpha / 1.2px blur for dot gain, and crisp
multiply printing. Source layers remain unchanged so cached artwork can be reused.
Do not flatten ink onto paper before this pass or replace it with generic grain.

The player then runs STYLE.finish once: the original anisotropic paper fibres,
low-frequency stock variation, grain seeded with 99+floor(t*12) at strength 0.03,
and a 0.07 brown vignette. Do not apply the finish twice. exField keys include all
noise parameters and dimensions; speckMask caches fixed-seed masks per size and
clips ring defects at canvas edges. Static caches are permitted; poses depend on t.

SWISS.rule(c,x0,y0,x1,y1,progress,width=2,colour=BLACK,head=true) draws hairline
flow arrows with solid heads. pict exposes example cat/dog silhouettes only where
appropriate; invent accurate isotype-like subjects for your lesson. arcField(c,x,y,t)
reuses the reference red disc and concentric arc segments, snapping to 22.5-degree
modules before a slow mechanical drift. Keep this motif subordinate to explanation.
SWISS.columnWipe(c,W,H_,elapsed,colour=RED) takes seconds since the wipe started:
12 columns close and reopen with 0.025s staggering. Swap underlying content at
~0.58s while covered; the wipe is clear by 1.2s. The takeaway can use black.

Shrink the hook into a running header; keep related ideas continuous. Use purposeful
page changes, ruled cause-and-flow diagrams, Inter 800 counting numbers and a red
block slammed behind the key result, reversing text to paper white. Study the
reference score for dry type taps, ruling-pen sounds, counter clicks, a 12-sheet
riffle during wipes and restrained sine chimes. Synchronize beneath narration.

The uploaded standalone HTML/storyboard instructions describe the reference.
The platform's approved lesson, measured narration, visualPlan, cueEvents and saved
review preference govern jobs. Author only animation.js with the trusted player;
do not impose the reference's topic, short duration or standalone approval flow.
