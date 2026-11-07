> Current visual generation uses the [versioned JavaScript style package](canvas-video-production.md).
> New creation requests require `style.visualStyleId`: `flat-vector-science`, `watercolor-wash`, `tech-glow`, `whiteboard`, `halftone-pop`, `risograph`, `gouache-poster`, `soft-3d`, `memphis`, `bauhaus` or `swiss-grid`.
> `style.reviewOutput` defaults to true and can be disabled for self-review.
> The prior tone presets have been replaced by an explicit visual-style selector;
> teaching tone, audience and voice remain independent. Review-only edits preserve speech.

# Course and lesson style

Creation accepts an optional free-form style description, optional audience and an
optional narrator ID. The same description can also appear in the learning prompt.
The dedicated style and audience fields take precedence over inferred preferences.
Presets are editable starting points, not exclusive style categories.

Draft creation persists the original preferences without calling a provider.
Outline preparation resolves them in one bounded model call using the selected
generation mode. This happens after the draft exists, outside a database
transaction, so usage can be recorded against the resource. Failures preserve the
draft for retry. The resolved style is saved atomically with the outline and is
reused by later stages. Fast uses the `openai/gpt-6-luna:fast` profile.

The versioned brief includes audience, summary, teaching approach, writing,
visuals, motion, pacing, narrator characteristics, vocal delivery and selected
voice ID/name. Every generation stage receives the same effective brief. Course
lessons inherit their course style unless an explicit lesson override exists.
Standalone lessons own their style directly. Audience remains independent of
tone and the course guide's teaching level.

## Editing and regeneration

- `POST /api/v1/lessons/{lesson_id}/style`
- `POST /api/v1/courses/{course_id}/style`
- `POST /api/v1/courses/{course_id}/lessons/{lesson_id}/style`

Send `style: {description, audience, voiceId}`, `expectedVersion` and
`generationMode`. For a course lesson, `style: null` restores course inheritance.
Version 0 represents no explicit style. Saves recheck the complete aggregate
after provider work and reject concurrent changes with HTTP 409. Standalone
routes also enforce owner identity. Reviewed course lessons retain their approved
style.

Voice-only changes retain the plan, script and approval, and invalidate audio,
alignment, animation and video references. Visual changes retain the plan but
invalidate the storyboard and downstream outputs. Teaching, audience, writing or
pacing changes also invalidate the plan. The existing durable per-scene speech
checkpoints can reuse unchanged speech inputs. Prior style and lesson snapshots
retain their artifacts; they are not deleted. History is bounded to 50 edits.
Course-level history is retained even before lessons exist. Existing JSON payloads
without style fields remain readable; no schema migration is needed.

## Narrators and expressive delivery

`GET /api/v1/voices?search=...` lists account-accessible narrators with descriptions,
labels and preview URLs. Catalog fetching paginates; provider credentials remain
server-side. The planner can select only returned candidates, and explicit voice
IDs are checked against the catalog. Retiring library voices are excluded.

An ElevenLabs key with speech permission but without `voices_read` uses the
configured narrator, with a visible explanation in the editor and saved brief.
If its accent metadata is unavailable, outline planning still proceeds and the saved
brief explicitly warns that the requested accent cannot be verified. Known accent
mismatches and unlabelled voices from a readable catalog remain rejected.
Enable `voices_read` on that key to browse account voices. Other catalog failures
return a retryable error rather than an empty or fabricated list. The application
default is Eldrin (`6WwXjDDEMyNmFG95zycZ`); an explicit environment override still
takes precedence for the configured fallback.

V4 delivery instructions are stored separately from spoken narration. The
ElevenLabs adapter inserts one bracketed direction per request chunk and maps
timestamps back to the clean transcript. It accepts provider alignment that
contains the exact injected prefix or omits it; other transcript changes still
fail. Tags never become caption words or cue anchors. Voice and delivery settings
participate in speech cache identity.

## Verification

Run frontend tests/build and the backend pre-commit gates. Style coverage includes
domain validation, stage propagation, inheritance/reset, selective invalidation,
history, ownership, optimistic concurrency, HTTP/database reloads, real local
provider contract servers, catalog permissions and tagged transcript alignment.
Frontend tests cover editable presets, independent audience, lazy voice previews,
versioned saves and retaining edits on errors.

For a live smoke test, create a one-minute standalone lesson in Fast mode and
choose a short, concrete topic. Review its style brief and outline, then generate
script, speech and animation. Reload to verify durable restoration. The platform
produces validated animation source; use the separate developer render workflow
in [animator-agent.md](animator-agent.md#developer-rendering-and-visual-review) to
render and inspect a test video without changing the application workflow.

### Live verification — 2026-10-29

A new one-minute rainbow lesson ran in Fast mode (`openai/gpt-6-luna`) with a
playful style for ages 8–10. The saved brief reached the outline, two-scene
storyboard, expressive Eleven v4 narration and animation. The script contains
119 words; measured narration is 55.52 seconds. Independent developer QA rendered
48 representative frames and a 1920×1080, 30 fps H.264/AAC video, checked repeated
seeks, inspected representative layouts/reveals and decoded both media streams.

The fresh app restored the saved animation and style. Explicit narrator selection
saved a second style version with prior media retained. Replaying speech and
animation after restart produced identical saved responses and zero additional
paid calls. The configured key lacks `voices_read`; the live configured-narrator
fallback and its UI explanation were verified, while full catalog pagination and
previews were exercised through real local HTTP contract servers.

Validation passed 448 backend tests, 105 frontend tests, 97.25% inner-layer unit
coverage, Ruff, mypy, both backend architecture gates, the frontend production
build and formatting checks. Private sample media and verification JSON are under
`backend/.artifacts/style-e2e/` and are not committed or published.
