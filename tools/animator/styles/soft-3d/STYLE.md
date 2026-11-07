# Soft 3D Clay · v1

Family: Dimensional. source-prompt.txt preserves the uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are unchanged. Draw accurate lesson-specific subjects, not the example's AI chip,
pets, bulb, cursor or invented statistics unless they fit the lesson.

Pastel matte-clay objects on a seamless lavender cyclorama: chunky rounded
extrusions, soft core shadows, bounce-light rims, glossy specular blobs and blurry
contact shadows. Fredoka 600/700 is bundled locally. Headlines >=44px, necessary
labels >=28px and key numbers >=64px at 1280×720; override smaller defaults.

CLAY exposes the reference roundedPoly, innerShadow, puffy, sphere, contactShadow,
clay, clayLabel, clayTube, pill, rrect and PAL helpers, plus example shape recipes.
puffy(ctx,{x,y,rot,s,path,rule,bb,face,side,ext,spec,fast}) uses Path2D, RGB palette
arrays, a local bounding box [left,top,right,bottom] and extrusion [dx,dy]. Preserve
all extrusion/core-shadow/rim/specular passes. clay wraps puffy with a PAL palette.
clayTube(ctx,start,control,end,progress,palette,width) builds puffy quadratic arrows;
clayLabel(ctx,x,y,text,palette,options) makes squishy pills. Both retain the original
shading. contactShadow belongs beneath objects and changes with their landing.
CLAY.background(ctx,W,H_,t) paints the original explainer's pastel sweep and glow.
The player applies STYLE.finish once: H.grain at 0.018 with seed 9+floor(t*12),
exactly as in the reference. Do not double-finish.

Use springy squash-and-stretch, gentle bobs at different depths, clay tube arrows,
squishy label pills and butter-yellow number badges. Dolly across a wide set with
parallax and restrained depth-of-field; pull back for the takeaway. Related objects
stay on the set as the camera moves. Derive every pose from absolute time; static
texture caches are fine. Study the sound score for rubbery squishes, small contact
puffs and gentle camera dollies. Align the largest hit to the key visible event.

The uploaded standalone HTML/storyboard instructions describe the reference.
The platform's approved lesson, measured narration, visualPlan, cueEvents and saved
review preference govern jobs. Author only animation.js with the trusted player;
do not impose the reference's AI topic, short duration or standalone approval flow.
