# Style-driven JavaScript video production

New lessons require an explicit `style.visualStyleId`: `flat-vector-science`,
`watercolor-wash`, `tech-glow`, `whiteboard`, `halftone-pop`, `risograph`,
`gouache-poster`, `soft-3d`, `memphis`, `bauhaus` or `swiss-grid` (all version 1).
The UI leaves the selection empty so creators explicitly choose one of the eleven styles.
Audience, teaching tone and narrator are independent preferences. The persisted
`style.reviewOutput` boolean defaults to true; turn it off to review the video yourself.

The pipeline is outline → scripting → frozen script → visual storyboard → measured
speech → one Canvas animation draft → offline visual evidence → optional independent consolidated AI
review → at most one repair → final rendering/technical validation → saved playback.
There are at most two authoring runs and one reviewer run per generation request,
including when a source-validation failure occurs; failures are surfaced for an
explicit retry rather than silently restarting agents. There is no Rive asset-production
stage and no React/Remotion authoring in this path. Old saved Remotion projects retain
their existing playback renderer for compatibility.

## Animation and review engine

Teaching references are selected from `tools/animator/teaching-examples` by
explanatory pattern, alongside the selected style. Both storyboarding and animation
receive the same annotated sequence and pixels; animation receives compatible source.
Only one teaching reference is supplied. When its source already implements the
selected style, it replaces the older full style example to limit context size.
Otherwise the style example supplies the medium and the teaching study supplies
choreography. Cross-medium history references supply notes and pixels rather than
incompatible drawing helpers. Changes to reference notes, source or pixels invalidate
authored-source caches. Increment the storyboard prompt version when changing
storyboard reference behavior, as with other storyboard prompt edits.

New review reports score style fidelity, illustration, composition, continuity,
explanation, visual development and pacing. Scores remain advisory. The reviewer
identifies specific subject-state changes and readable holds at measured cue times,
as well as layout defects; the single repair may address those findings locally.
The renderer supplies one bounded eight-frame motion strip per scene in addition
to existing contact sheets and closing frames. These ordered samples establish
sampled progression, not continuous motion or audio quality. Review/repair counts,
frozen narration and the delivery policy are unchanged.

Animation and visual review use direct OpenRouter calls exclusively. There is no
engine selector. The optional API field `animationBackend` defaults to `"direct"`;
`"codex"` requests are rejected before generation. Narration, source validation,
offline rendering, bounded repair, accounting and saved playback retain the same pipeline.
The worker has no Codex CLI dependency or provider credentials.

The direct author receives the approved inputs, measured timeline, style/runtime
code, curated example and reference pixels in one request and returns only
`animation.js`. The base style example follows the package manifest's order, while
the teaching reference matches the frozen explanation as described above. Packages
without a manifest retain deterministic selection. Invalid declared examples fail
instead of silently substituting another. Available `reference.png` pixels are
attached alongside the executable example. Reference selection participates in
the authoring cache identity. A targeted repair,
if required by review, is one separate request containing the source and consolidated
findings, including all per-scene observations and quality scores from fresh or
cached reviews. Source-validation or provider failures surface immediately without
another model call. The direct reviewer receives the reference, rendered contact sheets,
scene-closing frames, motion strips, measured timeline and visual plan in one request.
Its JSON report passes shared scene-coverage and score-schema validation.
Review disabled means the reviewer is not called; cached work makes no new model call.

Fast/Balanced/Pro selects the same model and reasoning profile for both agents. An explicit model override also applies to **both animation and review**.
Fast currently uses Luna Fast. The direct backend sends the base model with
`service_tier: "priority"` and retains the Fast variant in provenance and spend.
Saved projects record `backend`; legacy projects default to `codex`. New generation does not reuse legacy Codex artwork as a completed result. HTTP requests reject unknown engine values before any provider call.

Optionally run a paid direct Fast/Luna video against disposable persistence:

```sh
cd backend
PYTHONPATH=src poetry run python scripts/verify_animation_backends.py \
  --env-file /private/backend/.env --output-dir .artifacts/animation-backends
```

The run exercises real planning, speech, the selected author/reviewer, rendering,
saved metadata, byte-range playback and a fresh application with paid providers
disabled. Private results include the MP4, spend details and verification JSON.
Fresh planning requires the configured ElevenLabs key to have `voices_read` access.

## Versioned reference

`tools/animator/styles/flat-vector-science` contains the unchanged H harness and
SOUND kit from the user's reference, its exact shading/sky/finishing functions,
original reference animation, the approved Silk Roads illustration/choreography
example, local reference pixels, a style card and manifest. Nunito and Fredoka are
bundled locally. The package participates in generation identity and source hashes.
The player runs the original grain/mottling finish on every frame at original strength.

## Visual ownership and continuity

A dedicated scripting agent produces frozen narration first. The storyboard agent
adds visual-only direction without reviewing or rewriting that script. The saved
storyboard retains verbatim narration, speech anchors and educational constraints.
It adds stable object IDs, opening/closing composition, camera direction and continuity
from the previous segment. Narration segments do not mandate visual cuts.

One agent authors `animation.js`: `window.explainer(ctx,W,H,t)`, `window.scoreSound(k)`,
`window.visualPlan` and `window.cueEvents`. Logical coordinates are 1280×720; delivery
is 1920×1080 at 30fps. Every frame is derived from absolute time. The animator
produces a complete draft and checks source validity, without rendering previews
or running its own visual polishing loop. Cross-segment object continuity, camera moves and
transitions are possible because one renderer owns the complete visual timeline.

The storyboard and animator share the selected style. Scene directions identify
the focal subject, opening state, ordered cue-linked changes, settled result and
continuity. The animator plans meaningful intermediate key frames and uses staged
actions, suitable acceleration/deceleration, restrained follow-through and quiet
holds for reading. These are first-draft authoring improvements; the existing
reviewer prompt, inspection evidence, scores and repair policy are unchanged.

The trusted player, timeline, original narration, local fonts and reference package
are byte-protected. Only animation.js is authored inside the immutable project.
Preview images and implementation notes stay outside it. Frame rendering runs without
network or provider credentials. The renderer checks cue coverage/times, equation
strings, browser errors, repeated out-of-order seeks, scene/cue and periodic samples,
complete video encoding, dimensions/framerate/duration and full audio/video decoding.
Full encoding periodically collects discarded canvas/image buffers to keep long
render sessions within the worker memory budget. These checks establish technical
validity, not factual or aesthetic perfection.

Source validation also uses the TypeScript compiler's JavaScript name resolution
to reject undefined helpers with source locations, including calls in later scenes.
Before capturing frames or encoding, the renderer waits for the player's initialization
promise and readiness flag. Rejected initialization and browser errors surface with
their original message and source location; startup failures include failed local
resource requests instead of hiding them behind a generic readiness timeout.

## Sound

The same event constants drive picture and synthesized effects. The original sound
kit renders offline; the renderer mixes those effects underneath unchanged narration
at its measured offsets. No image, sound-effects or music provider is needed.
The plain-JavaScript preview player also supports narration, sound toggle, scrubbing
and looping. The narrator voice remains ElevenLabs.

## Review choices and provenance

With review enabled, a separate Fast/Balanced/Pro reviewer sees the style-reference
pixels, actual rendered contact sheets and individual frames. It reviews every scene,
including all seven quality dimensions described above (advisory scores 1–5).
The renderer's `review` mode captures periodic, scene, cue and transition samples
without encoding an intermediate full video. Scores are not acceptance thresholds;
locally repairable material weaknesses trigger the consolidated repair. The reviewer lists defects,
scene/timestamps and concrete corrections together. A rejection returns to the
visual author for one targeted repair using a dedicated repair prompt, without
regenerating narration or performing another visual inspection. Final delivery
always renders and decodes the full video. There is no second AI review.
`reviewStatus: repaired` records a repaired, technically verified delivery honestly;
it does not claim that the repaired pixels received independent AI approval.
Validated review decisions are saved before final encoding, so an interrupted
encode can retry without repeating the paid review. Partial files and videos
created or changed by the reviewer do not bypass final technical validation.
The reviewer judges timing against measured speech. Approximate outline durations
do not authorize trimming narration during visual repair.

With review disabled, the reviewer model is never called. Full rendering and technical
validation still run. Saved animation `reviewStatus` is `skipped`; the video UI labels
it as ready for the user's review. `approved` is reserved for a draft accepted by
the independent AI reviewer; `repaired` is shown separately in the video UI.
Changing only the review preference retains the outline, script, narration and source
cache. Review policy is part of delivery identity, so a skipped decision cannot be
mistaken for approval. Playback verifies source and rendered-video checksums and uses
the exact delivered file. Missing validated media produces an error, never silent QA
bypass. No generated video is automatically published.

## Code-first playback

Validated Canvas source is saved with `reviewStatus: pending` after the visual review
and any repair have selected the final source, immediately before MP4 encoding. First
drafts and intermediate repairs are not exposed. The existing page polling makes the
video watchable during encoding in both guided and automatic flows. Here `pending`
means delivery is still encoding, rather than that visual review is still running.
Pending playback remains private to the creator; public discovery continues to
require a finished delivery. When review is disabled or the existing advisory review
policy falls back with a warning, the selected source uses the same handoff.

The lesson page displays the selected source in the main player, with rendering
progress below it. Finished-delivery status is used for completion and
discovery, independently of playback availability. Recorded spending has its own
disclosure, expanded during generation so live animation, review and render rows
remain visible without opening thumbnail settings.

At initial load and on each play/resume, the player checks `/playback`. This endpoint
only inspects source and accepted media checksums; it never starts an encoder.
A finished MP4 uses the native video player. Otherwise `/preview?v=<source-hash>`
packages the exact drawing code, trusted runtime, fonts and narration for an isolated
Canvas player with play/pause, sound, seeking and fullscreen. It does not encode
another video. Audio and visual timing use the same saved timeline as the MP4.

An active preview stays on its current source when delivery completes.
The next play checks again and selects the current MP4 or source. Reload
also prefers a finished MP4. Preview completion supports watched/quiz progress while
encoding continues. Generation checks content edits independently and preserves
concurrent progress. If delivery fails, the saved code remains playable; continuing generation
reuses that source and the existing review cache. Concurrent lesson edits are checked
at each publication boundary and cannot be overwritten by late delivery.

The preview is served with private/no-store caching and a sandboxed Content Security
Policy. It contains embedded media and fonts, requires no provider credentials or
external network access, and cannot access the application origin.

Verify an existing real Luna Fast source through an isolated API, database, Redis,
and Chrome, with all paid providers disabled:

```sh
PYTHONPATH=src poetry -C backend run python scripts/verify_live_playback.py \
  --snapshot /private/saved-lesson.json \
  --source-project /private/animation/<input-hash>/result.json \
  --output-dir .artifacts/live-playback
```

Omit `--source-project` and supply `--env-file /private/backend/.env` to exercise
fresh authoring through the studio's explicit Luna Fast override. Both variants use
review disabled for the live encoding check; bounded review/repair remains covered
by the deterministic production tests. The verifier captures code motion, actual
narration playback, seeking, uninterrupted playback during encoding, MP4 selection
on the next play, byte-range delivery, reload, screenshots and browser errors.

## Install and test

```sh
poetry -C backend install --all-extras
npm --prefix tools/animator ci
npm --prefix frontend ci
docker build -t course-maker-animator:canvas-v1 tools/animator
docker build -f tools/animator/Dockerfile.playback -t course-maker-renderer:canvas-v1 tools/animator
```

Both images build natively on Apple Silicon; Rive CLI and x64 emulation are absent.
The UI framework remains React; generated video source is plain JavaScript.

Run unit/integration tests and the existing Ruff, mypy, hexagonal, tach and frontend
checks. The ordinary suite uses injected paid-provider fakes. For a real paid Fast
lesson in disposable database/cache containers, including both review settings and
fresh-app playback with provider keys disabled:

```sh
poetry -C backend run python scripts/verify_canvas_video.py \
  --env-file /private/backend/.env --output-dir .artifacts/canvas-e2e
```

After an interrupted delivery, add `--resume .artifacts/canvas-e2e/animation.json`
to repeat review/playback using the saved real script, narration and source.

Replay a saved real lesson through the browser with all paid providers disabled:

```sh
poetry -C backend run python scripts/verify_canvas_browser.py \
  --snapshot .artifacts/canvas-e2e/animation.json \
  --output-dir .artifacts/canvas-browser
```

This starts isolated persistence and an actual API/UI, verifies 1080p native video
playback and seeking, saves both review preferences in succession, regenerates using
the exact saved artwork, then reloads the lesson. It writes a screenshot and machine
readable results. It restores private timing metadata from the original artifact
directory; retain that directory alongside the snapshot.

The repository currently runs its course persistence adapter against MySQL; this
change does not migrate that existing database. Keep generated artifacts private.

## Live consolidated-review verification — 2026-10-30

A disposable API/database/cache and the actual browser UI generated **Why shadows
change length** with Fast mode, Luna, and review enabled. Measured narration and
delivered H.264/AAC video were 66.56 seconds, at 1920×1080/30fps. The run used
exactly one initial author, one independent review and one consolidated repair.
The reviewer identified faint shadows, overlapping comparison labels and a clipped
takeaway; the repair addressed the findings together without rendering previews.
The final source and video checksums matched the saved `repaired` delivery report;
the report did not claim independent approval of repaired pixels.

Browser checks covered actual playback, seeking, reopening during generation,
reload, the repaired-status notice, desktop/mobile layout and the creator's budget
table. Playback and reload added no model calls. Review and repair had separate
model, cost and duration rows. Offline render timing and playback were additionally
verified through a fresh production composition with no AI credentials; these
extra rendering probes contribute to the test lesson's cumulative rendering time.

Recorded provider spend was **$0.1734659**, including estimated narration conversion
for 425 speech credits, across 37 requests with no pending charges. Initial authoring
took 357.0 seconds, review 870.6 seconds and repair 254.5 seconds. This verifies the
bounded workflow and accounting; it does **not** establish a latency improvement.
Luna's high-reasoning model calls remained the dominant wait in this run.

Private evidence is in `backend/.artifacts/visual-review-smoke/`, including the final
video, delivery audit, browser result, budget screenshot and full spend response.

## Code-first browser verification — 2026-10-30

The existing “How the Moon changes shape” lesson was authored with the explicit
`openai/gpt-6-luna:fast` override. Its saved code and measured 58.16-second narration
then passed the isolated browser/API/database/Redis flow with paid providers disabled:
Canvas playback before MP4 readiness, audible narration, seeking, completion and
replay from zero, uninterrupted code playback while encoding, MP4 selection on the
next play, 1920×1080 delivery, HTTP 206 byte ranges and reload choosing MP4. Browser
JavaScript errors were empty. A separate browser probe also verified fullscreen.
The run used review disabled; it establishes playback behavior and technical delivery,
not independent visual approval. The delivery performed one MP4 encode; preview
packaging and playback checks performed none. Private evidence is in
`backend/.artifacts/live-playback-e2e-final/`, including `verification.json`, code/MP4
screenshots and the renderer's checksum/technical-validation report.

## How style storage and selection work

The UI lists the available styles and static reference thumbnails in
`frontend/src/course-maker/ui/StyleFields.tsx`. Selection updates the form's
`visualStyleId`; it does not fetch a prompt. Creation and style-edit requests send
that ID, and the backend validates it. The course/lesson's persisted JSON stores
the ID, `visualStyleVersion` and resolved teaching/visual brief. Course lessons
inherit course style unless overridden. Existing records default to Flat-Vector
Science v1; this addition needs no database migration.

Executable style packages live in `tools/animator/styles/<id>/`, alongside
`STYLE.md`, unchanged H/SOUND libraries, drawing helpers, full reference examples
and reference pixels. Each newly added style preserves the full uploaded prompt in
`source-prompt.txt`. Those reference instructions describe the medium; approved
lesson content, measured narration and the platform review setting govern jobs.

When animation authoring starts, CanvasAnimator copies the selected package into
the private job's `javascript/style/`. The author receives the brief and package;
trusted style files are protected from edits. Package bytes and inputs participate
in cache identity. Playback uses the saved job copy, including local fonts, rather
than re-fetching a catalog or calling a provider. `STYLE.fonts` declares which fonts
to preload and `STYLE.finish` applies the medium's final surface pass every frame.
Flat-Vector Science retains FV helpers; Watercolor Wash supplies WC wash, bloom,
pooled-edge and paper helpers. Tech Glow Explainer supplies TG neon diagrams, pulsing
connectors and the reference bloom/vignette pass. Whiteboard Explainer supplies WB
marker strokes, lettering, eraser ghosts and gloss/grain. Its STYLE.beginFrame
resets marker-tip tracking before every draw for deterministic seeking. Halftone Pop
Panel supplies HP comic devices and Ben-Day dots, separate colour/key plates
composited at the reference offset, and cached aged-paper/fibre-grain multipliers.
Risograph Zine supplies RISO separation canvases and the original ink-density,
halftone, misregistration, roller-streak and paper compositor; its finish is
inseparable from compositing, so STYLE.finish does not apply it twice. Gouache
Travel Poster supplies GP opaque paint masks with dry edges, chalky brush fields
and a matte board finish. Soft 3D Clay supplies CLAY extrusion, inner shadows,
bounce-light rims, puffy tubes and squishy labels with the reference grain. Their
Archivo Black, Space Mono, Bebas Neue, Oswald and Fredoka fonts are bundled locally.
Memphis Group supplies MEMPHIS thick outlines, hard shadows, terrazzo, geometric
patterns, sticker lettering and striped polka-dot band swipes. Its motion steps
at 12 fps and the trusted player applies the reference's full monochrome grain.
Rubik Mono One and Fredoka are bundled for offline playback.
Bauhaus Poster supplies BAUHAUS geometric forms, drop-on tags and bar-and-triangle
arrows on four independent knockout plates. It retains lithographic ink mottle,
plate misregistration, aged cream stock, fold scuffs, grain and vignette. Space
Grotesk and Syne are bundled locally; plate routing follows canvas save/restore.
International Typographic Style supplies SWISS modular grid geometry, concentric
arc fields, hairline arrows and column-by-column wipes. Its offset-print compositor
preserves source layers while applying ink dropouts and dot gain; the player adds
the reference paper fibres, animated grain and vignette. Inter 400/600/800 is
already bundled for offline playback.
Changing a style invalidates visual/downstream
outputs while retaining the outline and style history.

Adding another uploaded style currently requires a package, backend ID validation
and visual direction, a UI entry/thumbnail, and any new bundled fonts. There is
no database style catalog or runtime upload endpoint. Run focused unit and adapter
tests plus `node --test tools/animator/tests/style-runtime.test.mjs`; a live
provider/browser end-to-end run is separate.

## Persistent agent conversations

Migration `0013` adds `agent_sessions`. The configured SQLAlchemy database stores
PydanticAI 2.63 native `ConversationTypeAdapter` JSON, including tool calls,
results, structured-output messages, usage, and conversation identity. PostgreSQL
uses `postgresql+psycopg://...`; existing MySQL deployments remain supported.
Run `poetry -C backend run alembic upgrade head` before starting the updated API.
At startup, the API checks every mapped table and column and reports missing schema
with a migration instruction before it accepts generation requests. Source reloads
do not apply migrations; use `scripts/dev-main.sh` to rebuild and run the local
migration image when migrations change.
For MySQL deployments, configure `max_allowed_packet=256M` to persist native
reviewer conversations containing rendered image evidence; these can exceed the
server's default 64 MiB limit. The local Compose service uses this setting.
The PostgreSQL driver is now a production dependency; no provider thread is used.

Each session has a generated `agent_<UUID>` ID, owner, agent role, resource
(course/lesson), optional `job_id`, and revision. The server supplies the owner
from its existing identity dependency. A supplied session must match that user,
agent and resource. If a job ID is supplied on continuation it must also match;
omitting it retains the original association. Unknown or foreign sessions return
404. Two writers cannot overwrite the same revision; a stale save returns 409.
No database transaction stays open while a model or tool runs.
Explicit resumption fails if persistence has not been configured; it never silently
starts a new conversation. Review caches include the job scope, and a reused source
from a different job does not bring its producer session into that job's repairs.

Generation endpoints accept optional `sessionId` and `jobId` (snake_case is also
accepted). Omitting `sessionId` creates a separate conversation when an agent is
actually invoked; existing artifact caching can still avoid an invocation. For
the combined scripting/storyboard endpoint, `sessionId` selects the storyboard
conversation and `scriptSessionId` selects the scripting conversation. Animation
accepts a separate `reviewerSessionId`. A `message` supplies revision instructions.
The lesson response exposes IDs in `content.agentSessions` for standalone lessons
and `chapters[].lessons[].agentSessions` for courses: `outline`, `script`,
`storyboard`, `animator`, and `reviewer`. Syllabus responses expose the native
session ID as `session.sessionId`; old records retain their legacy course-ID
fallback until an agent creates a durable session.

The animator's review repair explicitly resumes the animator session that made
the draft. The reviewer has an independent conversation. Guide outline-edit tools
resume the current outline's producer session; they do not import the producer's
native history into the guide conversation. Interactive activity revisions resume
that activity's current producer session, scoped to its lesson and activity ID.
Quiz generation accepts and returns its own `sessionId`. Copying lessons and
activities clears producer-session links so copies remain independent.

Successful runs persist complete native history. Failed model calls leave the
last successful history unchanged. An artifact save that fails after a completed
agent call does not undo that recorded conversation. The store has no automatic
session lookup by user/lesson, new compaction, summarization, or checkpointing.
Older scripts/storyboards/animations have no recoverable native history; their
first session-enabled run starts with the supplied current artifact context.
