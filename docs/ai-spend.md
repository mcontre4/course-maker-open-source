# Lesson and course AI spend

Spend is a cumulative ledger of provider requests, separate from generated lesson
content. New plans, scripts, audio, and animations add charges to the same lesson.
Replacing content does not erase earlier charges. Cached stages make no paid
requests and add no entries. Tracking applies to new calls after migration 0004;
historical usage cannot be reconstructed from token totals alone.

Course spend is the sum of all lesson charges plus shared syllabus-generation
charges, which are shown separately as course planning. Charges for a lesson
removed from the current outline remain part of the course's historical spend.
Deleting a course deletes its ledger with the rest of its data.

## Billing sources

- OpenRouter: the actual `usage.cost` from each model response, including agent
  tool loops and output-validation retries. When absent, fetch `total_cost` from
  `/api/v1/generation` using that response's generation ID. No hardcoded model
  prices or account-balance differences are used.
- Direct animation and review: normal HTTP response hooks record OpenRouter usage
  inside separate direct worker scopes. No CLI billing relay runs. Cached animation
  source incurs no new spend. Historical CLI ledger entries remain readable.
- The Canvas pipeline records separate `animation`, `visual_review` and
  `animation_repair` worker scopes. The budget table shows the actual model,
  accumulated provider cost and elapsed time for each. The optional repair row
  appears only when the reviewer requests corrections. `render` records offline
  evidence generation, final encoding and verification time without inventing a
  model charge. Live worker scopes appear before the first billing response and
  finish on success or failure; cached stages add neither charges nor time.
- ElevenLabs: record provider-reported `character-cost` credits for every speech
  chunk, including chunks preceding a later failure. Configure
  `COURSE_MAKER_ELEVENLABS_USD_PER_CREDIT` with your effective account rate to
  convert these into USD estimates. Without it, speech credits remain visible and
  their dollar cost is pending. The rate is account-specific; the app does not
  assume a subscription tier or invent an invoice amount.

### Narration stays pending after generation

If the narration row shows credits but its USD amount stays pending, check the
running API's `COURSE_MAKER_ELEVENLABS_USD_PER_CREDIT`. A blank value means the
conversion rate is missing; waiting or refreshing cannot resolve it. Set the
effective account rate in `backend/.env`, then recreate the API container with
the same Compose files and project used to start it. A container restart alone
does not reload Compose environment variables. For the local development stack,
run this from the primary checkout (the one used by `scripts/dev-main.sh`):

```sh
export COURSE_MAKER_REPO_ROOT="$(git rev-parse --show-toplevel)"
docker compose -p course-maker-syllabus-ui --env-file backend/.env \
  -f compose.yaml -f compose.dev.yaml up -d --no-deps --wait api
```

Click **Refresh spend** on the lesson after the API is ready. Existing recorded
credits are converted and persisted as estimates; audio does not need to be
regenerated. Repeating the refresh does not duplicate charges. For example, at
the account rate recorded below (`0.0002` USD per credit), 379 credits become
`0.0758` USD. Use the rate for the actual account rather than assuming this
example applies to every subscription.

The ledger retains a pending entry before each in-process model request. A lost
response or ambiguous failure is pending, never silently zero. Definitive 4xx
rejections (except timeouts) are recorded at zero. Output-validation failures and
conflicting content saves do not roll back billing records. Provider outages
during reconciliation leave costs pending. Unknown request IDs cannot be
automatically reconciled. The animator journal remains private on disk; following
a worker process crash, rerun the same job to import its billing metadata.

Research/search tools, hosting, rendering, subscriptions, taxes and payment fees
are not model-token charges and are not included in the dollar sum. Future model
integrations must install equivalent request instrumentation.

## Architecture and API

The courses domain owns immutable `ModelCharge` values, decimal arithmetic and
summary rules. Application use cases open an injected `UsageTracking` scope only
around external generation calls. `SpendRepository` and `Billing` are inward-owned
ports. HTTP, SQLAlchemy and provider instrumentation remain adapters; composition
roots own client/session construction. Each ledger write uses an independent,
short session. No content transaction spans a model call or billing lookup.

- `GET /api/v1/courses/{course_id}/spend` returns USD totals, per-lesson totals,
  shared planning, per-stage/provider/model breakdowns, credits and token counts.
- `POST /api/v1/courses/{course_id}/spend/refresh` reconciles up to 100 pending
  calls and returns the refreshed summary. It never generates lesson content.

Spend is available only through internal tools. Money is represented as decimal
strings to retain sub-cent precision. User-facing course, preparation and lesson
pages do not render the spend table or fetch the spend ledger. Legacy spend
endpoints additionally require the internal key; account ownership alone cannot
read or reconcile spend.

During animation and visual review, the table keeps the recorded dollar amount
visible alongside `pending` and `processing`. For a first request this is
`$0.00 + pending`: it means no charge has been reported yet, not that the running
request is free. OpenRouter reports exact costs when each request completes;
completed requests remain included while later requests are pending. The UI
automatically retries pending OpenRouter billing with bounded backoff, including
after a worker finishes. **Refresh spend** remains available for later retries.
Speech credits without an account USD rate still require configuration.

Standalone lessons use the same ledger and display, including each chat revision
and every media stage. `GET /api/v1/lessons/{lesson_id}/spend` and
`POST /api/v1/lessons/{lesson_id}/spend/refresh` additionally validate the signed
lesson-owner cookie before reading or reconciling billing. Standalone charges
have their own lesson foreign key, are excluded from course totals, and cascade
with that lesson. Late pending writes and journal replays cannot erase a dollar
amount that has already been reconciled.

## Internal tools

Open `/internal/tools` directly; it is absent from user navigation. Configure a
separate, random `COURSE_MAKER_INTERNAL_TOOLS_KEY` of at least 32 characters on the
API server (Compose forwards this setting). Leave it empty to disable diagnostics.
Restart the API after changing it. Never reuse the service API key or put this
secret in a `VITE_*` variable. When accounts are enabled, sign in first.

Enter that key and a lesson ID, private lesson URL, public watch URL, or course
lesson URL. The tool can inspect lessons across owners and shows the existing
per-step agent, time and USD table, total spend, and total generation time. The
key remains in page memory and must be entered again after reloading.

`GET /api/v1/internal/lessons/{lesson_id}` reads diagnostics;
`POST /api/v1/internal/lessons/{lesson_id}/refresh` reconciles pending provider
billing without generating content. Both require `X-Internal-Tools-Key` and accept
optional `course_id`. Responses are not cached. Missing/invalid keys are rejected,
and an empty configured key disables the endpoints. The old course/lesson spend
endpoints also require the internal key in addition to their previous access checks.

Total generation time is the union of recorded step intervals, accumulated across
generations and retries. Overlapping parallel steps count once and idle gaps do
not count. Running steps use the current time; the tool polls while generation is
active. Missing timing records display **Unavailable**; historical records may be
partial. Per-step totals still sum each attempt, so their sum can exceed the total
when steps overlap.

Verification: `npm --prefix frontend run test:e2e -- internal-tools.spec.ts
--project=chromium` exercises desktop/mobile lookup, rejected keys, protected
legacy endpoints, billing refresh, course URLs, missing timing and missing lessons
against a disposable PostgreSQL database and the real HTTP/persistence adapters.
Provider billing uses a deterministic fake; this check makes no paid model calls.

## Reusable Constitution smoke test

Apply migrations, configure provider keys, and start the API and frontend as in
[the lesson setup](lesson-creator-agent.md). From `backend`:

```sh
PYTHONPATH=src poetry run python scripts/constitution_smoke.py --env-file .env
```

This idempotently seeds `tests/fixtures/constitution.json`: one ready course, one
one-minute lesson brief, and a saved course guide. It skips the syllabus agent and
makes no provider calls. Open the printed course ID in the UI and generate its
lesson plan. Then invoke the existing authenticated endpoints in order:

1. `/courses/{id}/lessons/generate` with `lessonId`.
2. `/courses/{id}/storyboards/generate` with `lessonId` and concise `visualStyle`.
3. `/courses/{id}/speech/generate` with `lessonId`.
4. `/courses/{id}/animations/generate` with `lessonId` and `visualStyle`.

Use the `/api/v1` prefix. Read `/spend` between stages and after reloading the
browser. Repeating cached stages must leave the call count and amount unchanged.
For another paid script/audio/animation run, seed with `--reset-storyboard`; this
retains the lesson plan and cumulative ledger. Use `--database-url` to target an
isolated developer database. This script is a developer fixture, not a public
endpoint. Never run it against user course data.

Speech duration is measured from generated PCM rather than assumed from the
script's word count. Inspect it before animation. Developer rendering remains a
separate review step described in [the animator documentation](animator-agent.md).

## Live verification — 2026-10-29

The standalone Constitution fixture ran through real lesson planning, script,
speech, and Codex animation providers. The initial 80-second narration was revised
to 126 words and 64.8 measured seconds. Both script/audio versions accumulated
under the same lesson. The supplied account rate was $2 per 10,000 speech credits
($0.0002 per credit).

| Stage | Requests | Recorded USD |
| --- | ---: | ---: |
| Lesson planning | 4 | 0.0280830 |
| Script & storyboard, including revision | 2 | 0.0633015 |
| Speech, including revision (798 credits) | 6 | 0.1596000 estimated |
| Animation | 15 | 0.3612559 |
| Total | 27 | 0.6122404 |

Course and lesson totals matched, with zero shared syllabus cost because the
fixture bypassed that agent. No charges remained pending. After restarting the
API, repeating all four generation endpoints returned cached content and an
identical complete spend response. Browser refresh restored the same totals and
provider breakdown. These are recorded results, not fixed future prices.

The animation passed source/type/timing checks. Separate developer review rendered
68 representative 1080p frames, checked repeated independent seeks across all
three scenes, and produced a 64.811-second H.264/AAC review MP4 (64.8 seconds of
canonical content). Representative scene frames were inspected. Generated media,
the full spend response and verification JSON remain private in
`backend/.artifacts/constitution-review/`. This does not publish or attach video
to the platform's lesson player.

All 333 backend tests and 79 frontend tests passed; domain/application coverage
was 97.66%. Ruff, mypy, both backend architecture gates, frontend boundaries and
the production frontend build passed.
