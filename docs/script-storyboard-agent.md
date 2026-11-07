# Scripting and storyboard agents

Generation uses two independent agents in sequence:

approved lesson outline → scripting → frozen script → visual storyboard → measured speech → animation.

Storyboarding and animation now share a selected teaching reference from
`tools/animator/teaching-examples`: a compact annotated sequence, rendered frames,
and executable choreography. Deterministic matching uses frozen narration,
learning purposes and equations to choose a mechanism, comparison, worked example,
procedure, network or institutional-change reference. Matching is identical before
and after storyboarding; unknown material falls back to the mechanism study.
The selected style card remains authoritative for the artwork medium. The Silk
Roads and Brazil references preserve the latest saved sources with explicit
improvement targets; their imperfect frames are not a visual finish standard.

Each new cue has concise `focus`, `relationship`, `action` and `hold` fields:
what to notice, what becomes understandable, what visibly changes, and what settles
for inspection. Provider output requires these fields. They persist through domain,
HTTP DTOs and animation/review input. Legacy cues default the three new fields to
empty strings and retain their original narration hashes; narration edits retain
the visual metadata while updating speech anchors.

Both run behind the existing storyboard generation endpoint. Course and standalone
studios keep their current API, saved artifacts and regeneration controls. No
migration is required. Existing storyboards remain readable and cached; regenerating
from script runs both new agents. Changing a prompt does not rewrite saved lessons.

## Ownership

`script_prompt.md` owns the spoken explanation: factual fidelity, intermediate
reasoning, audience, terminology, natural delivery, beat coverage and pacing. It
returns a `LessonScript` containing immutable `ScriptSegment` values. A segment has
an ID, teaching beat, learning purpose, verbatim narration, duration estimate,
required equations and an optional generic `visual_intent` of at most 500 characters.
It has no composition, camera, transition, cue or sound fields. All script editing
happens in this call.

`storyboard_prompt.md` receives that frozen script and the selected visual style.
It does not review, critique, fact-check or request revisions to the script. Its
strict output schema contains visual fields only: scene ID, visual brief, stable
object IDs, opening/closing compositions, speech-anchored actions, camera direction,
continuity, transitions, short labels and accessibility notes. It cannot return
narration, beat assignments, objectives, equations or duration changes. The adapter
copies these values directly from the script and validates exact preservation.
Whitespace in narration is retained.

One visual entry corresponds to each frozen narration segment, in the same order.
Several visual shots may unfold within a segment through its ordered cue actions;
a shot or camera move can continue across audio boundaries. This avoids coupling
visual editing to TTS segmentation.

## Visual direction

The storyboard agent plans the whole film's visual progression and specific
original illustrations. Directions cover establishing/medium/close-up framing,
viewing-angle changes, tracking, pans, push-ins, pullbacks, layered depth/parallax,
object transformations, match cuts, object-led wipes and medium-appropriate
transitions. Each action identifies its focal subject, development, camera,
settled result and label/object entrances and exits. Object identity can persist
while its composition changes; old annotations should leave before they cause clutter.

The prompt asks for sophisticated motion with clear preparation, development,
emphasis and settling, balanced with readable holds. Camera and presentation
easing must preserve scientific meaning. Canvas 2D can imply depth and alternate
views; a 3D engine or new external assets are not required. Missing geographic
assets are handled as explicitly labeled relational schematics.

Sound directions share the anchored visual events: restrained material textures,
filtered air, plucks, structural impacts and resolving tones. Sounds remain below
narration and do not require external providers. The animator implements those
instructions using the selected executable style and bundled SOUND kit.

The storyboard is not an extra script-editing pass. The independent rendered-output
reviewer remains responsible for the existing bounded presentation review.

## Validation and provider behavior

`ScriptedStoryboardAgent` adapts the existing external generation port to the two
provider stages. Composition constructs distinct `PydanticScriptAgent` and
`PydanticStoryboardAgent` scopes, schemas and prompts. Each receives the selected
Fast/Balanced/Pro profile or general model override. Scripting receives the outline
and guide; storyboarding receives the frozen script, guide and selected style,
without the editable outline.

The domain enforces script identity, objective and beat coverage, required equations,
unique segment IDs, positive duration estimates and a broad 90–200 word planning
range per target minute. Estimates total the requested duration within 30 seconds.
Storyboard conversion requires every frozen segment exactly once and in order.
Cue anchors must occur exactly once, case-sensitively, in that segment's narration;
cue IDs are unique and anchors follow spoken order. Model-added script fields and
invented timestamps are rejected.

Each provider stage permits two correction retries, four total requests, 100,000
total tokens and a 240-second run timeout. Output is capped at 24,000 tokens and
individual provider requests at 180 seconds; automatic HTTP retries are disabled.
A visual correction retries against the same frozen script. A scripting failure
prevents any storyboard call. Either failure preserves previously saved content.
Missing selected style references fail before either paid call.

Both calls happen outside database transactions. Saving retains the existing
revision/concurrency checks and atomic persistence. The saved metadata version is
`script-1/storyboard-9`; generation usage aggregates both calls. Spending and timing
record independent `script` and `storyboard` stages, displayed separately in the UI.

## Review-to-repair handoff

A rejected rendered review passes its complete `feedback`, `scene_checks` and
`quality` fields into repair instructions, including on a cached rejection. Concrete
fixes and timestamps stored only inside per-scene observations are preserved.
This retains the existing one-review/one-repair policy and immutable narration.

## Verification

Offline tests exercise both real Pydantic AI schemas with injected provider models,
script preservation, correction/failure behavior, model overrides, all five style
references, HTTP/database round trips, cached retrieval and actual repair-request
payloads. Unit tests exercise frozen script invariants without infrastructure.
Run the backend suite with disposable Docker services available:

```sh
poetry -C backend run pytest -p no:tach -q
poetry -C backend run ruff check src tests scripts/verify_canvas_video.py
poetry -C backend run mypy
poetry -C backend run python scripts/check_hexagonal_boundaries.py --root src
poetry -C backend run tach check
```

For an explicitly authorized paid end-to-end smoke, the existing verifier creates a
one-minute synthetic Silk Roads lesson in disposable MySQL/Redis, calls real planning,
scripting, storyboarding, speech, animation and review providers, renders the video,
checks unchanged narration and byte-range playback, then verifies playback through
a fresh app with paid providers disabled:

```sh
poetry -C backend run python scripts/verify_canvas_video.py \
  --env-file /absolute/path/to/backend/.env \
  --output-dir /absolute/private/output/directory
```

The verifier accepts either independent approval or a repaired delivery and reports
the actual status. Structural and offline checks establish workflow correctness;
a newly generated video's aesthetic quality requires inspecting the real result.

### Live verification — November 2, 2026

A one-minute synthetic Silk Roads lesson passed real planning, scripting,
storyboarding, ElevenLabs speech, Canvas authoring, independent review and final
delivery through disposable MySQL/Redis. Scripting and storyboarding recorded
separate provider steps. The result contained three frozen narration segments,
153 spoken words, 17 aligned cues and 16 visual-plan shots. Measured speech was
64.64 seconds; the H.264/AAC delivery was 1920×1080 at 30 fps. All three narration
WAV checksums matched the alignment, and narration stayed unchanged through
animation, review and fresh-app retrieval. The independent reviewer approved the
draft; no repair was required by this sample.

Chrome verification with paid providers disabled passed playback, seeking, HTTP
206 ranges, saving the review preference, cached delivery with unchanged artwork,
reload and an empty JavaScript-error list. The browser driver was updated for the
current Edit video, Quality & speed and Visuals controls. Private evidence is in
`backend/.artifacts/split-agents-e2e/`, including the final MP4, rendered frames,
review report and machine-readable generation/browser verification. This is one
workflow smoke sample, not a comparative aesthetic benchmark; the review-to-repair
regression is separately covered by fresh and cached rejection tests.
