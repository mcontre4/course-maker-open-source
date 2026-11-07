# Memphis Group · v1

Family: Art & Design Movements. source-prompt.txt preserves the uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are unchanged. Draw accurate lesson-specific subjects rather than carrying over
the example's AI totem computer, pets or illustrative statistics.

Early-80s Memphis Milano maximalism: pastel pink, mint, lilac, butter and cream
clash with magenta, primary blue, yellow, teal and red (see MEMPHIS.PAL). Use thick
#151515 outlines, hard offset shadows, squiggles, zigzags, dot grids, terrazzo chips
and confetti triangles. Rubik Mono One 400 and Fredoka 700 are bundled locally.
Headlines >=44px, necessary labels >=28px and key numbers >=64px at 1280×720;
override smaller reference defaults, especially tag's default size of 22.

MEMPHIS.solid(ctx,path,fill,shadow=10,lineWidth=5) preserves hard shadows and thick
outlines. squigglePath and zigzagPath return Path2D draw-on strokes; strokeOutlined
adds their original outline and hard shadow. terrazzo retains seeded polygon chips.
roundRect, bubble, burst, fatArrow, tag, chunky, confetti, dotCard, quarter and
gridCard expose the reference's geometric drawing/lettering recipes. chunky uses
Rubik Mono One; tag uses Fredoka. Shape recipes for the example's face/machine are
available only where appropriate; invent your lesson's own props in this medium.

MEMPHIS.background(ctx,W,H_,scene=1,grounds=null) draws the original cached pastel
split, 260 seeded bacterio dashes and edge/corner decorations. Scenes 1–4 supply
different ground palettes and decor arrangements. Optional grounds is a pair of
CSS colours; the cache includes scene, colours and dimensions. sceneGround returns
the underlying canvas. These logical layouts assume 1280×720. Keep the centre clear
for the explanatory subject and adapt decoration where necessary for readability.

MEMPHIS.celTime(t) quantizes to floor(t*12)/12, matching the reference's on-twos
feel. Derive all poses, pop/overshoot, squash-and-stretch, off-beat bobs and draw-ons
from that absolute time. Maintain related subjects across beats. For scene changes,
MEMPHIS.bandSwipe(ctx,W,H_,progress) draws the original rotating stripe/polka-dot
band with its hard shadow. Progress 0 and 1 leave the canvas untouched; swap the
underlying scene near the middle of the swipe. Use the reference's ~0.85s sweep
as a starting point, with the scene swap at ~0.42s. Draw persistent headers last.

The player applies STYLE.finish once: the original monochrome H.grain at 0.05,
seed 6+floor(t*12). Preserve its full strength and don't apply it twice. Study the
reference score for rubbery pops, sticker slaps, outlined arrow steps, band swipes
and a large starburst hit. Keep effects synchronized beneath narration.

The uploaded standalone HTML/storyboard instructions describe the reference.
The platform's approved lesson, measured narration, visualPlan, cueEvents and saved
review preference govern jobs. Author only animation.js with the trusted player;
do not impose the reference's topic, short duration or standalone approval flow.
