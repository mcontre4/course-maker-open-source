# Course-generation pipeline

Course request → syllabus and course guide → lesson outline → scripting agent →
frozen narration → visual storyboard agent → ElevenLabs speech and measured
alignment → one plain-JavaScript
Canvas animation agent → offline rendering and technical validation → optional AI
visual review/repair → saved video playback. Publication is a separate explicit action.

A visual style must be explicitly selected. The first package is Flat-Vector Science,
based on the user's exact drawing helpers, finishing passes and Silk Roads example.
The selected versioned style reaches storyboarding, visual authoring and review;
scripting focuses on spoken teaching. Teaching tone, audience and narrator remain
independently configurable.

The animation agent authors topic-specific illustrations and motion in one draft.
The platform renders representative frames for the optional independent reviewer;
the author does not run a visual preview loop. It owns cross-segment camera moves
and object continuity; audio segment boundaries do not require visual cuts.
No mandatory asset agent or Rive/React/Remotion scene authoring runs for new lessons.

Measured narration is preserved through visual repairs. Deterministic time-based
Canvas rendering, cue coverage, local fonts, original sound synthesis, stream metadata
and complete decoding are checked. Final AI review defaults on; users can turn it off
for self-review. A skipped review is recorded and displayed honestly and never counts
as AI approval. Versioned caches and checksum-bound video playback preserve artifacts.

See [JavaScript video production](canvas-video-production.md),
[storyboard](script-storyboard-agent.md), [lesson planner](lesson-creator-agent.md),
[style editing](lesson-style.md), and [speech timing](tts-alignment.md).
