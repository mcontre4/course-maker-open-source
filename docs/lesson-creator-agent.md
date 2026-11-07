# Lesson Creator Agent

Implements stage 2 of [the course generation pipeline](course-generation-pipeline.md).
Pydantic AI uses OpenRouter's Responses API and a Tavily research tool. The
existing syllabus provider keys are reused. General text generation stages use
one server-owned generation profile selected with `generationMode`:

| Mode | Model | Reasoning |
| --- | --- | --- |
| `fast` | `anthropic/claude-sonnet-5.5` | `medium` |
| `balanced` (default) | `anthropic/claude-opus-5.5` | `medium` |
| `pro` | `anthropic/claude-opus-5.5` | `max` |

These profiles apply to scripting, storyboards, animation authoring, and AI review.
The Animator model dropdown overrides animation authoring and AI review.
The separate Generation model dropdown
covers outlines, lesson content, storyboards, style planning, and guide chats
(including summaries and guide-triggered generation). It is saved as a browser-wide
preference and sent through the allowlisted `X-Generation-Model` request header;
composition injects it into general agents for that request only. Automatic follows
the selected generation profile. Image generation, speech, and offline rendering
keep their own dedicated settings. Explicit model overrides retain the mode's
reasoning effort: medium for Fast and Balanced, max for Pro.

## Engagement and pacing defaults

Scripting opens with a supported question, contrast or consequence and develops it
into a payoff. Storyboarding and animation sustain interest through visible discovery,
meaningful reframing and focused reveals. Narrator style planning favors an expressive,
conversational voice and brisk but unhurried phrasing, respecting explicit preferences
and sensitive subject matter. Difficult ideas retain reading time and brief pauses;
no stage may add facts, rush speech or alter measured audio to increase energy.

These defaults adapt [TikTok's creative guidance](https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads)
on early hooks and narrative structure, [Guo, Kim and Rubin's observational study](https://doi.org/10.1145/2556325.2566239)
on online-video engagement and informal delivery, and [Brame's educational-video review](https://pmc.ncbi.nlm.nih.gov/articles/PMC5132380/)
on conversational speech, signaling, segmentation and removing distractions. Advertising
attention and viewing engagement are not proof of learning; these are editorial defaults,
not a guaranteed retention formula or a required cut cadence or speaking rate.

Narration guidance lives in script phrasing and voice/style selection. The current
ElevenLabs adapter does not send free-form delivery metadata as spoken text or inject
bracketed performance directions. Saved narration remains unchanged until regenerated.

Both model dropdowns offer the same choices, including Claude Opus 5.5 Fast
($8 input / $40 output per million tokens). Anthropic's
[fast-mode documentation](https://platform.claude.com/docs/en/build-with-claude/fast-mode)
lists Opus 5.5 support, with no beta header; Sonnet 5.5 is not supported.
[OpenRouter service tiers](https://openrouter.ai/docs/guides/features/service-tiers)
accept `service_tier: "fast"` for Anthropic fast capacity. The application `:fast`
suffix is removed before sending provider requests; GPT fast choices use
`service_tier: "priority"`. Provider billing reports actual usage and tier costs.

The UI offers Fast / Balanced / Pro before course and standalone lesson creation,
syllabus refinement, lesson planning, and standalone video generation. Preferences
are saved in this browser per course/lesson; course lessons inherit the course
choice until overridden. Each generation request sends the chosen mode explicitly.
The mode applies to future generation, never replaces a cached artifact, and does
not change the speech synthesis provider or rendering. Unknown/null modes return
422 before an AI call. Legacy per-stage `COURSE_MAKER_*_MODEL` overrides have been
replaced by these profiles.

## Purpose and output size

The Lesson Creator is a specialized syllabus designer for one lesson. It decides
the teaching sequence and supplies short bullets on what to cover or show, ready
for the Script & Storyboard Agent to expand. It does not write the lesson text,
full explanations, narration, or a detailed storyboard.

Planning starts with the selected video duration and audience. The agent chooses
an achievable central takeaway, budgets a comfortable timeline, then selects the
scope, examples and depth that fit those teaching beats. Shorter lessons cover a
focused slice of the subject; longer lessons can develop more depth. Time for
grounding, connections, examples and understanding visuals belongs inside the beat
allocations. The 120–150 spoken words per minute guide limits content load rather
than setting a word-count target. Overfilled beats trigger scope reduction or
timeline rebalancing, never rushed speech or skipped reasoning.

For standalone lessons, only the generic title concept and automatically supplied
`Understand <title>` objective identify the subject, so ordinary topic lists and
broad learning wishes can be prioritized and deferred in `scope_boundaries`.
Specific brief concepts/objectives remain mandatory even in course copies and
manually edited standalone outlines. Explicit learner requirements, earlier agreed
requirements (unless explicitly relaxed) and approved course objectives remain
mandatory. Only a conflict between those requirements and the fixed budget should produce an
`infeasible` plan. That plan retains the mandatory coverage and supplies an
explanation plus a longer-duration recommendation; it does not change the selected
duration or start automatic media generation.

Style planning controls presentation and must not invent required curriculum.
Inferred topic, equation and example suggestions in the guide's style are optional,
including those in older saved styles. The creator's original style request is
labeled separately so explicit coverage requests remain authoritative. A broad
one-minute topic must not be rejected because an inferred teaching style suggests
a more comprehensive survey.

New plans target 300–500 authored words, with a hard limit of 600 (excluding the
preserved lesson ID, objectives, concept labels, and source metadata). They contain
at most six teaching beats, each with 1–3 teaching-note bullets capped at 50 words,
a short purpose and check/answer cue. One compact example has at most three
solution milestones and a checked result. Facts, equations, prerequisites,
misconceptions, and scope boundaries stay brief and avoid duplicating the beats.
The agent validator requests a shorter output when the size limits are exceeded.
These generation limits do not invalidate previously saved plans or change the
stored/HTTP shape. Saved plans remain cached; this change applies to new generation.

## Run locally

Install backend dependencies with `poetry -C backend install --extras ai` and
frontend dependencies with `npm --prefix frontend ci`. Configure `backend/.env`
using `backend/.env.example`, start MySQL and Redis, and apply migrations with
`poetry -C backend run alembic upgrade head`. This checkout retains the existing
MySQL persistence adapter; lesson plans are stored in the course aggregate JSON
and require no new table or migration.

Start the backend with:

```sh
poetry -C backend run uvicorn app.main:app --app-dir src
```

Start the UI with `npm --prefix frontend run dev`. The UI defaults to the real
API. Its development proxy reads the API bearer key from `backend/.env` on the
server and forwards `/api` to `http://127.0.0.1:8000`. Override the target using
`COURSE_MAKER_API_TARGET`. Provider keys and the API key are never included in
browser JavaScript. Production hosting must supply an authenticated same-origin
API proxy; Vite's development proxy is not part of a static production build.
Set `VITE_DEMO_MODE=true` only for the original standalone demo.

Create a course, generate its syllabus, approve it, open a lesson and click
**Generate lesson plan**. The UI displays progress, provider errors, the saved
teaching progression, examples, understanding checks and research sources.
Reloading retrieves the persisted plan without another LLM call. If initial syllabus
generation fails or requests clarification, the saved draft opens a recovery form.
Retry or reply there; the existing course and revision are reused.

## HTTP contract

Authenticated `POST /api/v1/courses/{course_id}/lessons/generate` accepts
`{"lessonId": "lesson_<UUID>", "generationMode": "pro"}`. Omit `lessonId` (or the body) to select the first
lesson. It returns the updated `CourseView`; each lesson has a nullable `plan`.
HTTP plan fields use camelCase, following the rest of the API; stored artifacts use snake_case. The same plan is
returned by the existing course and lesson GET endpoints. A lesson with a saved
plan returns it without spending provider credits again.

Generation requires an approved syllabus and its saved curriculum/course guide.
The agent receives one lesson brief, chapter outline, previous/next briefs, guide,
and video time budget. Manually edited topics and video minutes take precedence.
It must preserve objectives and IDs and cover every approved concept. Feasible
plans allocate integer beat seconds totaling exactly the requested video duration.
Infeasible plans retain honest estimates exceeding that budget and recommend the
sum rounded up to whole minutes. Research, model requests,
and total tokens are bounded; research is optional, and cited URLs must come from
returned Tavily results. Generation
has a 180-second timeout, six search calls, twelve model requests and a 100,000-token
limit. Provider clients are created and closed on the operation's event loop.

The application closes its read transaction before external calls and locks and
rechecks the course and curriculum before saving. Concurrent edits return 409;
missing lessons return 404; absent credentials/provider failures return 503.
Failed calls leave saved content intact. Model ID and request/search/token usage
are persisted with the plan. Teaching changes invalidate the plan along with
existing media. The current approved-course policy prevents syllabus edits.

This stage creates a teaching plan only. It does not create final narration,
storyboards, audio, animation, quizzes, or video. The tutor `/chat` route remains
unimplemented. Do not retry an ambiguous network failure automatically: first
reload the course to check whether the plan was saved.

## Verification

Offline model-routing checks run with:

```sh
poetry -C backend run pytest -p no:tach tests/integration/generation tests/integration/animation -q
```

These exercise HTTP validation and real use cases with fake outgoing AI ports,
SDK request serialization through a fake HTTP transport, and animator commands
through a recording runner. They do not call live LLMs or generate a real course.


Run backend pytest, Ruff, mypy, both architecture gates, and the frontend tests
and build. Deterministic tests cover plan invariants, use-case failure/concurrency,
real Pydantic AI tool execution, MySQL round-trips, cached HTTP generation and
missing credentials. The regular tests explicitly disable live provider keys.
For live verification, use the UI flow above with configured keys, check the saved
`plan_generation` model/tool/token usage, and reload the lesson after restarting
the API. Expect real provider usage and charges for uncached generation.

An opt-in paid smoke test uses disposable MySQL and Redis, the real lesson agent,
and the real scripting agent for the one-minute case:

```sh
LESSON_TIMING_LIVE_ENV_FILE="$PWD/backend/.env" \
LESSON_TIMING_LIVE_OUTPUT="$PWD/backend/.artifacts/lesson-timing-live" \
poetry -C backend run pytest tests/integration/runtime/test_live_lesson_timing.py -q -s
```

It checks the same broad beginner topic at one and five minutes, explicit
mandatory-scope and saved-specific-objective conflicts, exact beat budgets,
approval gates, script handoff and restoration in a fresh app without paid
providers. Saved outline and script JSON
support qualitative review of the selected scope and pacing. This smoke excludes
speech synthesis and video rendering; browser workflow tests cover the downstream
UI/media flow with deterministic providers.

The pendulum cases additionally exercise real style planning and the Fast lesson
model, reuse an older style that suggests excessive coverage, and verify that
explicit coverage in a creator's style request is still preserved. These cases
use deterministic thumbnails and do not request media generation.
