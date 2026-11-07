# Halftone Pop Panel · v1

Family: Print. source-prompt.txt preserves the full uploaded prompt;
examples/reference-ai.js preserves the complete executable reference. H and SOUND
are bundled unchanged. Reuse the medium with subjects accurate for the approved
lesson; do not carry over the example's robot, AI topic or invented statistics.

Use thick tapering black brush outlines, flat primary yellow, staggered red/blue
Ben-Day dots, off-white aged stock, hand-lettered balloons and bold Bangers type
(400, bundled locally). Palette: red #e2231a, blue #1f5fbf, yellow #ffd51f,
black #141210, white #fbf6ea. Headlines >=44px, necessary labels >=28px and key
numbers >=64px at 1280×720. Override smaller defaults in reference helpers.

HP exposes the unchanged benday, box, balloon, burstPath, burst, say, sayK,
popIn, fatArrow, speedLines and panel helpers. Create separate colour and key
plates with HP.plates(W,H_): use c for fills/dots and k for black outlines/type.
Paint the complete frame on these plates, applying the same camera to both.
HP.composite(ctx, col, key, W, H_) composites the colour plate at (+2.5,-1.5)
and the key plate with multiply, exactly as in the reference. Never flatten the
plates before misregistration. panel() returns a callback that restores the
contexts and draws the thick panel border; call it after painting the panel.

The player runs STYLE.finish once, using the original cached paperAge recipe:
low-frequency yellowing, edge ageing and seeded fibre-grain multipliers at their
original strength. Do not apply the paper pass twice. Ben-Day dot gain is in
the drawing helper and remains part of the ink, not an optional overlay.
Every frame is computed from t with H.rng/H.makeNoise; static texture caches
are permitted. Allocate or clear plates per frame so seeking is deterministic.

Read one comic strip panel by panel; pull back to gutters during camera moves.
Use fat yellow arrows to show relationships, captions/balloons that slam in word
by word, Bangers counters bursting out of explosion balloons and brief meaningful
shake at the key emphasis. Keep related objects continuous within each panel.
Study the reference score for short thwacks, burst impacts, ratchets, counter clicks
and soft page slides. Align effects to visible events beneath narration.

The original standalone storyboard/HTML instructions are reference material.
The platform's approved lesson, measured narration timeline, visualPlan and saved
review setting govern production. Author only animation.js with the trusted player;
preserve measured narration rather than imposing the example's short duration.
