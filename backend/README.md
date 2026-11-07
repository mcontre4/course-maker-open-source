# Backend

Application backend organized as a modular monolith using hexagonal architecture.

## Layout

- `src/app/<domain>/domain`: entities, value objects, domain services, and domain errors.
- `src/app/<domain>/application`: one application service per use case.
- `src/app/<domain>/ports`: repository and external-service interfaces.
- `src/app/<domain>/adapters`: incoming HTTP and outgoing persistence, cache, and third-party implementations for that domain.
- `src/app/main.py` and `src/app/<domain>/composition.py`: composition roots that bind ports to adapter implementations.
- `migrations`: Alembic database migrations for the database adapter.
- `tests`: mirrors `src/app` after the test-type split; for example, user tests live under `tests/unit/users` and `tests/integration/users`.

Run the API from this directory with `uvicorn app.main:app --reload` after installing the project dependencies.

## Architecture and code quality

Credit balances, purchase history, Stripe Checkout, webhook fulfillment and generation
charges are documented in [credits setup and pricing](../docs/credits.md).

All backend features must follow hexagonal architecture: `adapters -> application -> domain`.
Each business domain is an independent bounded context under `src/app/<domain>`; it must not
import another domain. Share stable primitives through `app/shared`, or communicate through
explicit events when cross-domain coordination is needed.

Keep domain entities, value objects, invariants, and domain services pure and independent of
frameworks or infrastructure. Each application service implements one use case through a
single public `execute(Request) -> Response` method, using frozen DTOs and injected ports.
HTTP adapters validate and translate transport data; persistence and external-service adapters
implement ports. Only composition roots construct and wire infrastructure.

Keep modules cohesive and methods short, with one clear responsibility. Extract named helpers
for nested mapping, validation, and orchestration rather than building large methods or generic
multi-operation services. Business rules belong to the domain; transaction boundaries belong
to application use cases. Never hold a database transaction open during external API calls.

Test domain and application behavior with deterministic, explicitly injected fakes. Test adapters
against their real dependencies separately. Monkey patching is forbidden. Ruff, mypy, the
hexagonal boundary checker, and `tach check` must pass, and their always-on pre-commit and CI
gates must remain enabled.

## Lesson quizzes

Apply migrations with `poetry -C backend run alembic upgrade head` before running
the updated API. Migration `0010` adds quizzes and learner attempts in separate
tables, so editing or generating a quiz does not change the lesson/video revision.

The owner API supports `GET` and `PUT /api/v1/lessons/{id}/quiz` and
`POST /api/v1/lessons/{id}/quiz/generate`. GET returns `null` when no quiz exists.
PUT replaces all questions, sets `origin: edited`, and accepts `expectedRevision`
(`0` for a new quiz). Generation accepts `generationMode` and `onlyIfMissing` and
sets `origin: generated`. Question fields are `id`, `kind: multiple_choice`,
`prompt`, `options`, `correctIndex` and `explanation`.

The quiz agent starts in its own worker when scripting starts in either lesson
flow. It uses the outline plus any saved storyboard/narration, records the `quiz`
spend stage, and cannot overwrite concurrent outline or quiz edits. An existing
quiz is retained until the creator explicitly regenerates it. Quiz failures leave
media production running; generation can be retried from the Quiz tab.

Published lessons expose `GET /api/v1/published/lessons/{id}/quiz` without answer
keys or explanations. `POST .../quiz/submit` accepts `quizRevision` and ordered
`answers` and returns server-computed scores and feedback. `GET .../quiz/attempts`
returns the current learner's history, with `limit` and `offset`. Attempts retain
their quiz snapshot, so later edits do not change old scores. Learner identity
uses the signed anonymous-owner cookie by default, or an authenticated account session when accounts are enabled. Copying a lesson copies its quiz,
but not learner attempts.

Run deterministic coverage with `poetry -C backend run pytest tests/unit
tests/integration/lesson_quizzes`. An opt-in paid smoke test uses a disposable
PostgreSQL/Redis pair and the real Fast quiz agent:

```sh
LESSON_QUIZ_LIVE_ENV_FILE=/private/backend/.env \
LESSON_QUIZ_LIVE_OUTPUT=.artifacts/lesson-quiz-live \
poetry -C backend run pytest tests/integration/lesson_quizzes/test_live_quiz.py -q -s
```

## Lesson interactives

Apply migration `0011` with `poetry -C backend run alembic upgrade head`.
Interactives are independent of lesson media and the existing `content.interactive`
field. Creators can build them before an outline or video exists. Both standalone
and course lessons use the same globally unique lesson ID and owner authorization.
Owner endpoints use the legacy API key and signed anonymous-owner cookie by default. Set `COURSE_MAKER_AUTH_ENABLED=true` to require account sessions and CSRF protection for writes.
See [account authentication](../docs/authentication.md) for setup and provider configuration.
All JSON uses camelCase.

Under `/api/v1/lessons/{lessonId}/interactives`:

| Method | Path | Body / result |
| --- | --- | --- |
| GET | base | `{items: Interactive[]}` in lesson order |
| POST | base | `{brief, generationMode?}`; returns the building interactive (201) |
| GET | `/{id}` | Poll build progress and fetch current/published HTML |
| PATCH | `/{id}` | `{title, goal, prompts, expectedRevision}`; details go live immediately |
| DELETE | `/{id}` | Delete the interactive and its versions (204) |
| POST | `/{id}/changes` | `{instruction, expectedRevision}`; build a new version |
| POST | `/{id}/build/retry` | Retry the failed request |
| POST | `/{id}/build/cancel` | Discard the running build; retain a retryable failure |
| POST | `/{id}/versions/{n}/restore` | `{expectedRevision}`; select a saved version |
| PUT | `/{id}/published` | `{version: number or null}`; choose/remove the learner version |
| PUT | `/order` | `{ids: string[]}`; every lesson interactive exactly once |

The response includes `id`, `lessonId`, `brief`, `title`, `goal`, `prompts`,
`revision`, `createdAt`, `updatedAt`, version metadata (`number`, `request`,
`createdAt`), `currentVersion`, `html`, `publishedVersion`, `publishedHtml`,
`build: {request, startedAt, stage} | null`, and `failure: {request, message} | null`.
Build stages are `reading_lesson`, `designing`, `building`, `checking`.
Completion bumps the revision. Stale revisions and concurrent builds return 409.
Restoring retains later versions; the next build uses the next highest number.
Failed or cancelled builds preserve saved current and published pages.

The server trims text and enforces 10 interactives per lesson, a 2000-character
brief, 1000-character change instruction, required title up to 80 characters,
goal up to 200, and up to six nonempty prompts of 160 characters each. Generated
HTML is limited to 512 KiB (UTF-8). The AI adapter uses the quiz model profiles and
allowlisted model override header. Configure OpenRouter and install the `ai` extra
to build pages. The first build supplies a title, goal and 2–4 things to try;
Creator edits saved during the first build take precedence over generated
details, and subsequent builds preserve them.

Builds run in an application-owned worker pool with fresh operation sessions,
independent of the initiating request. No transaction stays open during an AI
call. A persisted build token prevents duplicate or cancelled jobs from saving.
Owner reads and mutations recover abandoned builds after a 15-minute lease,
turning them into retryable failures. Enqueue failures are retryable immediately.
Usage is recorded under the `interactive` lesson AI spend stage (and the parent
course when applicable).

`GET /api/v1/published/lessons/{lessonId}/interactives` is public and applies the
published lesson visibility rule. It returns only selected published pages in
lesson order: `{id, lessonId, version, title, goal, prompts, html}`. Drafts, briefs,
requests, failures and history never appear. The frontend displays the page in an
`allow-scripts` iframe with its restrictive offline CSP. Copying as the owner
retains history and publication selections but clears running jobs; other users
receive only published pages. Source lessons remain unchanged. Parent deletion
cascades; removing a nested course lesson also removes its interactives.

Production uses HTTP adapters. `VITE_DEMO_MODE=true` retains the browser sample.
Run `poetry -C backend run pytest tests/unit/courses/lesson_interactives
tests/integration/lesson_interactives` and `npm --prefix frontend run test:e2e --
lesson-interactives.spec.ts --project=chromium` for deterministic coverage of the
API, real PostgreSQL persistence and browser workflow.

An opt-in smoke test builds and refines a real page, verifies publication isolation
and records provider spend using disposable PostgreSQL:

```sh
LESSON_INTERACTIVE_LIVE_ENV_FILE=/private/backend/.env \
LESSON_INTERACTIVE_LIVE_OUTPUT=.artifacts/interactive-live \
poetry -C backend run pytest tests/integration/lesson_interactives/test_live_interactive.py -q -s
```

## Video production

New course and standalone lessons use direct OpenRouter LLM calls for Canvas animation,
optional independent visual review, and one consolidated repair. Offline Docker workers
validate source and render video without network access or provider credentials.
Codex CLI is no longer installed or used. Saved legacy projects remain readable.
See [Canvas setup and verification](../docs/canvas-video-production.md).
