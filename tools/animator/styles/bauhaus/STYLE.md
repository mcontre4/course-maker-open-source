# Bauhaus Poster · v1

Family: Art & Design Movements. source-prompt.txt preserves the uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are unchanged. Invent accurate geometric subjects for the approved lesson rather
than carrying over the robot, pets, AI topic or illustrative statistics.

Primary red #cf3a2a, yellow #efb526, blue #1f4f9b and black #1c1a18 on aged cream
#ece2c9. Use a strict grid, circles, squares, semicircles, triangles and constructed
lettering. Space Grotesk 400/700 and Syne 800 are bundled locally. Headlines >=44px,
necessary labels >=28px and key numbers >=64px at 1280×720. Override small defaults.

Create a fresh frame with BAUHAUS.plates(W,H_): it returns {c,layers}. c is the
reference's vector drawing proxy over four transparent colour plates, ordered
yellow/red/blue/black. Use only BAUHAUS.C colours for fillStyle/strokeStyle. Every
fill, stroke, rectangle or text draw inks its own plate and knocks the same shape
out of the others. Cream knocks out all plates, exposing paper. Apply camera
transforms to c; save/restore preserves its fill/stroke routing as well as canvas
state. Frames own independent plates. Use this vector proxy for shapes and text;
it is not a full canvas/image/gradient/compositing API.

BAUHAUS.composite(ctx,frame,W,H_) paints the original aged cream stock, then prints
the colour plates at offsets yellow (+2,-1), red (-1.5,+1), blue (+1,+2), black (0,0).
It runs the original inkify pass with seed 21, mottle 0.22 and speck 0.004 and
multiplies the ink onto the paper. Do not flatten the plates before this pass or
substitute a flat cream background. exPaper supplies seeded fibres, edge ageing
and foxing; cachedField keys include all dimensions and field parameters.

The player then applies STYLE.finish once: the original explainer fold creases,
260 seeded fold scuffs, monochrome grain at 0.06 with seed 9+floor(t*12), and the
0.18 brown vignette. The standalone hero uses a slightly stronger grain; production
uses the explainer's exact recipe. Do not add any finishing pass twice.

exArrow draws bar-and-triangle flow arrows; exTag drops Space Grotesk tags onto
what they label. ring draws annular geometry. letter is the reference's partial
constructed alphabet (only b, o, r, t); use Space Grotesk for arbitrary lesson text,
or construct additional accurate glyphs. exCard/exRobot are example shape recipes.

Build one long Bayer-style information-design sheet. Track along it with purposeful
continuous pans, retain grid rules and related subjects, then pull back to reveal
the explanation as one diagram. Stamp shapes and counters with restrained overshoot,
draw arrows on, drop tags onto their subjects and circle the key moment in red.
Derive all poses from absolute time and H.rng/H.makeNoise. Study the reference
score for wooden block taps, type sorts, drafting-sheet slides, counter clicks and
warm resolving marimba hits; synchronize them beneath measured narration.

The uploaded standalone HTML/storyboard instructions describe the reference.
The platform's approved lesson, measured narration, visualPlan, cueEvents and saved
review preference govern jobs. Author only animation.js with the trusted player;
do not impose the reference's topic, short duration or standalone approval flow.
