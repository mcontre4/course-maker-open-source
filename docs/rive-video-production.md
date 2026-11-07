> Historical Rive/Remotion design. Codex CLI authoring and review adapters have been retired; new generation uses the [direct Canvas pipeline](canvas-video-production.md). Saved legacy playback remains supported.

# Rive illustrated video production

Historical implementation notes. New lessons use the
[plain-JavaScript Canvas pipeline](canvas-video-production.md); the current worker
images no longer install Rive CLI. The commands and architecture below describe the
previous pipeline and are retained for understanding legacy artifacts.

## Responsibilities

1. Teaching agents create an outline and verbatim script/storyboard through Pydantic AI.
2. ElevenLabs produces unchanged narration and measured speech alignment.
3. A separate Codex visual-production agent generates per-lesson RML sources, Rive
   binaries, a concrete design system, named animations and a scene/asset manifest.
4. The Remotion animation agent assembles these illustrations, measured labels,
   equations and charts on the canonical narration timeline.
5. An offline renderer captures cue/transition frames, checks repeated out-of-order
   seeks and produces a fully decoded H.264/AAC video.
6. An independent Codex reviewer receives actual rendered contact sheets and reviews
   every scene. The application permits one repair, routing artwork defects to the asset agent and layout defects
   to the compositor while retaining narration and timing; repeated failure raises a controlled unavailable error.

`ProduceIllustratedAnimation.execute(Request) -> Response` coordinates the three
ports. Both existing generation entry points use the production facade, so callers
cannot accidentally skip the rendered gate. The individual source adapter remains
separately testable. Legacy saved projects can still play through the playback port.

## Dynamic artwork and motion

Rive is the default for illustrated objects, people, machines, environments and
processes. There is no preapproved stock-art collection. The asset agent authors
shapes and custom paths, groups, named timelines and appropriate bones/constraints.
The design system includes palette, typography, spacing and motion conventions.
SVG/D3, KaTeX and Three remain available for precise graphics appropriate to a topic.
Lottie is installed for local animation data. Do not force all tools into a lesson.

Asset contracts specify IDs, covered scene IDs, description, animation names,
controls and at least three review times. Sources remain editable alongside binaries.
Internal motion must agree with measured speech cues; labels and equations remain
in Remotion so they can be measured and progressively disclosed. Inter fonts and
all WASM/assets are bundled locally. No image-generation provider is required.

## Installation

```sh
poetry -C backend install --all-extras
npm --prefix tools/animator ci
npm --prefix tools/animator/template ci
# The pinned Rive CLI only distributes Linux x64; Docker emulates on Apple Silicon.
docker build --platform linux/amd64 -t course-maker-animator:rive-v1 tools/animator
docker build -f tools/animator/Dockerfile.playback -t course-maker-renderer:rive-v1 tools/animator
```

`compose.dev.yaml` builds the workers. The generation image includes Rive CLI 1.8.0,
Codex CLI, the pinned visual toolkit, Chromium, FFmpeg and Pillow. The native render
image has no provider credentials and runs without network access. Both retain bounded
CPU/memory/time and separate writable workspaces. Agent jobs use the chosen mode:
Fast uses `anthropic/claude-sonnet-5.5` for animation and review, and
`openai/gpt-6.1-terra:fast` for the other text generation steps. Balanced uses
`openai/gpt-6.1-sol:fast`; Pro uses `openai/gpt-6.1-sol`.
Provider credentials remain in the configured backend environment; never put them
in source projects or committed evidence.

Rive CLI binaries are downloaded from the publisher, with a pinned SHA-256; this
repository does not assert that the authoring CLI is open source. Runtimes have their
own MIT license. Script-free local `--once` builds work without account login.
Embedded Luau/AnimaScript/shaders are deliberately rejected because their shipping
path requires signing. No jobs log in, sign, upload or publish.

## Offline Remotion integration

The pinned `@remotion/rive` component downloads WASM from a CDN. Instead, the
adapter-owned `RiveIllustration.tsx` uses the pinned low-level Rive runtime and local
WASM. It disables asset CDN and creates a fresh artboard for each sampled frame,
applying the named timeline at absolute frame time. This avoids accumulating seek
history and keeps arbitrary frame rendering deterministic. Generated agents cannot
modify this helper. No live state machines or clock-driven scripts run during video.

## Acceptance and caching

- `.assets/<input-hash>/assets`: generated RML, binaries, design tokens and manifest.
- `.asset-state/`: authoritative checksums outside the coding worker mount.
- `<input-hash>/remotion`: immutable inputs/audio/runtime plus editable scenes.
- `.reviews/<review-hash>/render`: rendered frames, contact sheets, MP4 and probe evidence.
- `.review-state/`: independent decisions bound to the exact source hash and video SHA-256.

Source validation, render validation and visual approval are separate evidence.
`animation_ready` returned through the production facade requires all three.
A source checksum alone is insufficient. Playback reuses the approved MP4 only when
its source hash, renderer version, bounded local path and video checksum match.
No narration is regenerated for a visual repair, and no database transaction remains
open during provider calls or rendering. Job caches permit reuse after interruption.
The review is model-based, not a guarantee that every possible scientific illustration
is correct. Test new subject categories and inspect complex motion in actual videos.

## Real short-lesson end-to-end check (paid providers)

From `backend`, with configured OpenRouter and ElevenLabs keys:

```sh
poetry run python scripts/verify_illustrated_video.py \
  --env-file /private/path/backend/.env --output-dir .artifacts/rive-e2e
```

The script creates fresh disposable MySQL/Redis containers (the current runtime's
configured database adapter), applies migrations, and exercises HTTP draft creation,
real Luna outline/storyboard, actual ElevenLabs speech, Rive asset authoring, Remotion
assembly, independent review, persisted results and full/range video playback.

For recovery after a late rendering failure, `--resume-project /path/to/project.json`
accepts an `AnimationProject` checkpoint alongside the saved `speech.json` and project
inputs in that output directory. It verifies source checksums, reruns source validation
and the independent rendered review, restores the completed lesson into a fresh
disposable database, and checks HTTP animation lookup plus full/range playback.
It reuses the real completed narration and artwork instead of charging for them again.
Review failure still stops acceptance.

## Local verification result

The Fast/Luna lesson “How a crank moves a piston” produced three dynamically
authored Rive assets and a 98.24-second narrated composition (the request targeted
one minute). Real outline, storyboard, speech, asset and compositor calls completed.
A renderer entry-point bug was caught and fixed; the run resumed from those real
completed artifacts rather than regenerating narration or artwork.

Independent review received 50 cue/transition frames plus full-resolution scene
closing states. Small label-padding and motion-envelope placement fixes were made;
the final candidate passed review. Its 1920×1080, 30fps H.264/AAC MP4 decoded fully,
passed repeat-seeking checks, and the exact approved video was returned through
HTTP 200 and byte-range 206 playback. Nine sampled narration windows matched the
original audio with correlation above 0.98 and timing offsets below 0.4ms.

The result is a clear, restrained engineering schematic. Artistic richness remains
limited, and character anatomy was not tested by this lesson. Initial Luna asset
authoring took about 29 minutes; x64 authoring-worker emulation and repeated previews
also made the first assembly slow. Prompts now bound correction/preview passes and
the default per-worker deadline is 1800 seconds. This verifies the local pipeline,
not production hosting timeouts or quality across every illustration category.
The sample is a one-minute crank-and-piston lesson; all selectable teaching/visual
calls use Fast mode. Outputs and failures are saved privately under the chosen folder.
Never substitute fabricated narration or timings for this verification.

## Focused runtime probe

Compile `tools/animator/tests/fixtures/rive` with `rive <directory> --once` in a
writable temporary copy, then run `verify-rive.mjs PROBE.riv OUTPUT RiveIllustration.tsx`
in the native renderer image with the repository tools mounted. It proves offline
WASM loading, visible motion, and identical repeated frames after out-of-order seeks.
Python unit tests cover orchestration, bounded repair and rejection; adapter tests
cover filesystem handoffs/integrity, and Node tests check actual TypeScript boundaries.
