# Animation production

New lessons use one plain-JavaScript Canvas animation agent with the versioned
Flat-Vector Science reference package. The agent owns illustration, internal motion,
composition, camera movement, transitions and synthesized sound. No separate Rive
asset agent runs and generated scenes use no React or Remotion.

See [the complete contracts, review options, installation and verification guide](canvas-video-production.md).

The script owns teaching facts and verbatim narration; ElevenLabs owns measured timing.
The storyboard supplies explicit object continuity and camera/composition direction.
The platform first renders key frames using the same drawing code as the final video.
Offline rendering and technical validation always run. The user's saved review setting
controls the independent final AI reviewer and its bounded repair opportunity.

Legacy saved projects retain playback support. Codex CLI authoring, review and
billing-relay adapters have been removed.

## Animator model selection and research (October 30, 2026)

Course and standalone studios offer an optional **Animator model** override before
video generation. Automatic follows the mode: Fast → Claude Sonnet 5.5 at medium
effort, Balanced → Claude Opus 5.5 at medium effort, Pro → Claude Opus 5.5 at max
effort. Scripting and storyboard agents use the same profiles. Clearing the selection
restores Automatic. Explicit animator and reviewer overrides retain the mode's effort.
The override is sent only for video/animation requests, is validated
against a server allowlist, and applies to plain-JavaScript illustration, animation,
repairs and independent visual review through direct LLM calls. Changing a selection alone
does not regenerate an existing video. A subsequent generation request with a
different explicit model authors new source; review-only changes reuse
matching artwork. Model selection is local to the current studio visit. Animation and review always use direct LLM calls.

Base API prices, USD per million tokens:

| Model | Input | Output | Suggested positioning |
| --- | ---: | ---: | --- |
| GPT-6 Luna | $0.10 | $0.50 | Budget previews |
| GPT-6 Luna Fast | $0.20 | $1 | Budget previews with priority processing |
| GPT-6.1 Terra | $1 | $5 | Balanced production candidate |
| GPT-6.1 Terra Fast | $2 | $10 | Balanced production with priority processing |
| GPT-6.1 Sol | $2 | $10 | Higher quality coding candidate |
| GPT-6.1 Sol Fast | $4 | $20 | Higher quality coding with priority processing |
| Claude Sonnet 5.5 | $2 | $10 | Quality alternative; evaluate alongside Sol |
| Claude Opus 5.5 | $4 | $20 | Premium candidate for complex scenes and repairs |
| Claude Haiku 5.5 | $0.10 | $0.50 | Budget alternative; base rates up to 100K prompt tokens |

Sources: [OpenAI pricing](https://developers.openai.com/api/docs/pricing),
[Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing),
and the [OpenRouter public model catalog](https://openrouter.ai/api/v1/models).
The direct backend uses Chat Completions without tools. Fast choices use
application-only `:fast` identifiers, stripped from the upstream model with
`service_tier="priority"`. This applies to authoring, repair and independent review.
Automatic follows the generation mode, and an explicit override applies to both agents.

Haiku prompts above 100K tokens cost $0.50 input / $2.50 output per million
tokens. The selector displays this threshold when Haiku is selected.
These are base rates, not a fixed video quote: context tiers, caching, reasoning,
repair attempts, and provider charges affect the total. Illustration and animation
share one author; review, speech and rendering add separate costs. Displayed UI prices are a dated snapshot;
update the frontend catalog when rates or available versions change.

For illustration, 20,000 uncached input tokens plus 10,000 billable output tokens
cost about $0.007 for Luna, $0.07 for Terra, $0.14 for Sol or Sonnet, and $0.28 for
Opus. This is one hypothetical model call, not a forecast for a complete lesson.

### Evidence and recommendations

There are benchmarks closer to this task than general coding leaderboards:

- [cliphou.se October Remotion benchmark](https://cliphou.se/benchmark/2026-10/)
  provides a fixed 12-second TSX brief, source, request settings, rendered videos,
  timing and cost. Sonnet 5.5 and Opus 5.5 both passed on the first attempt, as did
  Sol and Luna. It is a small task sample, not a reliable ranking of lesson-video
  quality. Its full time-to-video includes rendering, which can dominate latency.
- [MotionBench](https://motionbenchmark.com/) offers complete editable motion
  graphics attempts and costs. Its September trials are explicitly unranked;
  completion evidence should not be presented as a quality leaderboard.
- Berkeley's [Animation2Code](https://anya-ji.github.io/animation2code-website/)
  evaluates 1,069 reference animations reconstructed as HTML/CSS/JavaScript.
  Its tested models usually execute successfully, but temporal similarity remains
  weak. It measures reconstruction rather than our narrated, storyboard-driven
  creation task and tests older models; its scores do not rank current variants.

Sonnet and Opus are useful additions to trial, but there is insufficient evidence
to promise either is best for our videos. Anthropic positions
[Sonnet 5.5](https://www.anthropic.com/claude-sonnet-5-5) for faster, well-scoped
work and Opus for complex open-ended work. That supports testing Sonnet as a
quality alternative and Opus as a premium option; it does not prove visual quality.

A further candidate is **Gemini 4 Argon**: the October Remotion example passed on
its first attempt, and [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing)
is currently $2 input / $10 output per million tokens, increasing to $4 / $20 on
December 1, 2026. It is not in this initial selector; verify the complete worker
and review workflow before expanding the allowlist.

Keep mode defaults until a local comparison uses the same approved storyboards,
styles, narration and retry limits across models. Judge readability, timing,
factual fidelity, animation quality, render success, latency, and total billed
cost per accepted video. The model-selector change used deterministic tests for HTTP
contracts, application propagation, routing and production configuration. The Canvas
pipeline also has real Fast-mode generation and browser playback verification;
see the linked Canvas guide for those commands.
