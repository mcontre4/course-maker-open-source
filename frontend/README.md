# Course Maker frontend

React and TypeScript frontend for creating courses, producing narrated lessons, and exploring learning material.

## Run

For the primary-checkout development UI on port 5173, run from the repository:

```sh
sh scripts/dev-main.sh
```

The script resolves the primary Git checkout even if invoked from a worktree.
It starts the Docker API on port 50050 using `compose.dev.yaml`, mounts the primary
checkout's backend source read-only, and enables Uvicorn reload (including Python
and agent prompt Markdown changes). Polling supports Docker Desktop file changes.
It then runs Vite from that same checkout on port 5173 with the Docker API as its
proxy target. Stop an existing server on 5173 before running it; strict port
selection prevents silently starting on another port. Existing database volumes
are retained under the `course-maker-syllabus-ui` Compose project.
Dependency changes require rerunning the script to rebuild the image; schema
changes require migrations. The base Compose configuration keeps reload disabled.

```sh
cd frontend
npm ci
npm run dev
```

Start the backend first using `backend/.env` (see the root README):

```sh
docker compose --env-file backend/.env up -d --build api
```

Vite proxies `/api` to `http://127.0.0.1:8000`. By default it supplies the private server-side API key and forwards the signed anonymous-owner cookie; enabling accounts switches to HttpOnly account cookies. Set `COURSE_MAKER_API_URL` and `COURSE_MAKER_API_PORT` in `backend/.env` if using another API port; restart Vite after changing connection settings. Set `PORT` to choose a frontend port. When accounts are enabled, `COURSE_MAKER_AUTH_PUBLIC_URL` must match the browser origin exactly. See [account setup](../docs/authentication.md) for Google and email configuration.

Production hosting must rewrite application routes to `index.html` and provide a same-origin `/api` gateway to FastAPI, forwarding cookies and Origin unchanged over HTTPS. The Vite development proxy is not part of the static build. The legacy gateway supplies the service key server-side. When accounts are enabled, FastAPI enforces account sessions and the gateway must stop supplying that key.

## Stack and state

- React + TypeScript + Vite for the client application.
- React Router for course, syllabus, lesson, and quiz navigation. The current lesson is a URL parameter; quiz mode is a search parameter, so back/forward navigation works.
- TanStack Query caches application read models and invalidates course queries after writes. Remote data does not live in Context.
- React Hook Form + Zod validate form input. Domain functions independently enforce duration and completion rules.
- React state owns transient video error, quiz, and topic-composer state. Context injects a stable application port; it does not become a global data store.
- Plain responsive CSS follows the existing repo styling approach, with Manrope and the Figma palette. Reduced-motion preferences and keyboard navigation are supported.

## Hexagonal architecture

```text
src/course-maker/
  domain/       Pure readonly models, duration rules, syllabus invariants, quiz grading
  application/  Single-execute use cases, inbound/outbound ports, request/response DTOs
  adapters/
    http/        FastAPI transport, response validation, and read-model mapping
    demo/        Sample outlines and quizzes, plus the Figma lesson coverage data
    persistence/ Versioned, validated browser storage implementing CourseRepository
  ui/           Incoming React adapter: routes, forms, query hooks, view components, CSS
  testing/      Explicit, deterministic fixtures
  composition.ts  Constructs adapters and injects them into use cases
```

Dependencies point inward: `ui → application → domain`; outgoing adapters implement application ports and translate external data into application read models. The UI never imports repositories, browser storage, generators, or domain entities. Application responses omit quiz answer keys. Use cases contain no React, browser globals, fetch, storage, time, or ID generation.

`src/main.tsx` is the browser composition root. It injects fetch into the HTTP adapter and constructs the application and QueryClient once, outside React renders. Tests inject explicit backend or transport fakes.

`npm run check:boundaries` uses the TypeScript AST to enforce layer imports, inner-layer infrastructure isolation, and one public `execute()` per use case. It runs during every build and in frontend CI.

## Connected syllabus flow

The default application uses FastAPI for the course library, draft creation, syllabus generation, manual topic changes, approval, and persisted conversation history. The form saves a draft and opens its permanent syllabus URL before requesting generation. Its description is sent unchanged as the first agent message. Follow-ups use the same course session and its current revision. Reloading restores server history; a revision conflict refreshes the saved course and lets the learner review before retrying. Failed generation keeps the saved draft and the message available for retry. No mutation is automatically retried.

After approval, open a lesson to generate its researched teaching plan. The HTTP adapter validates and preserves the complete plan, including teaching beats, examples, and sources.

The syllabus displays outcomes, warnings, learning objectives, planned weeks, video minutes, and separate practice, reading, and review budgets. Agent source URLs are clickable. Approval saves the plan; video and quiz generation remain separate work. Lessons without a video URL or saved animation source show the not-ready state.

The local-storage/demo factory remains available to isolated tests and explicit `VITE_DEMO_MODE=true` development sessions. API mode is the default and its browser data is not migrated into the backend. Illustrations remain local SVG assets.

## Checks

```sh
npm run build
npm test
npm run check:boundaries
```

Tests cover duration limits, topic invariants, review/quiz completion, DTO boundaries, repository errors, and complete UI flows including persistence after remount. Dependencies are replaced through injection, not monkey patching.

## Agent chat and rich answers

Lesson, course, script, and animation guides share assistant-ui's external-store
runtime, message primitives, and composer. TanStack Query and the existing guide
API still own saved history, revisions, request identities, pagination, and retry.
Legacy lesson and syllabus chat surfaces use the same message renderer.

OpenUI Lang renders answers using a small, display-only library: `Answer`,
`Explanation`, `Steps`, `Comparison`, and `Callout`. Markdown history, code blocks,
and short replies remain supported. Invalid or incomplete OpenUI shows a recovery
message with the original source available; generated output does not run HTML,
JavaScript, queries, mutations, or application actions. The OpenUI renderer loads
on demand. Keyboard input supports Enter to send and Shift+Enter for a newline;
failed sends retain the draft.

After editing `src/course-maker/ui/assistant/answer-library.tsx`, run
`npm run generate:answer-prompt` and commit the generated backend `answer_prompt.md`.
The backend supplies these instructions to every guide role. The production build
checks that the prompt matches the library.

Run the browser tests with Docker available:

```sh
poetry -C ../backend install --extras ai
npx playwright install chromium webkit
npm run test:e2e
```

Playwright builds and previews this worktree's production frontend and starts a FastAPI test server with a
disposable PostgreSQL container. It exercises real HTTP, agent execution, and SQL
persistence with a deterministic model provider; no live AI credentials or paid
model requests are needed. It covers all four guide roles, reloads, independent
chats, rich answers, Markdown, invalid output, and mobile layout. Screenshots and
failure traces are written to the ignored `test-results/` directory. Account menu
navigation also runs with mobile Chrome and mobile Safari touch emulation.

## Finished lessons

Finished lessons open in a learner preview with their video and saved interactive.
`Edit lesson` selects `?edit=1`, exposing the full studio while keeping the media
visible. `View lesson` returns to the learner preview; refresh and browser history
preserve the chosen mode. Unfinished lessons keep opening in the studio.

An existing video URL takes precedence. Saved Remotion animation source uses the
same-origin, authenticated lesson playback endpoint. The first request renders
an H.264/AAC video in an offline Docker worker; subsequent requests reuse the
cached render. Source, narration, revision, and AI spend are unchanged. Standalone
playback checks the authenticated account owner. Byte ranges support seeking.

`scripts/dev-main.sh` builds the playback image as part of local startup. For a
manual backend startup, first run:

```sh
docker build -f tools/animator/Dockerfile.playback -t course-maker-renderer:rive-v1 tools/animator
```

The local adapter needs Docker access and a shared absolute animation directory
when running in a sibling container. Production can serve an existing video URL;
a remote rendering/storage service should implement the `LessonVideo` port when
Docker is unavailable.

Account sign-in is opt-in through the backend's `COURSE_MAKER_AUTH_ENABLED` (default `false`).
The frontend reads `/api/v1/auth/config` at runtime and uses the previous anonymous-owner flow
when disabled. Restart the API and Vite after changing backend environment configuration;
no frontend rebuild or separate auth flag is required. See [account setup](../docs/authentication.md).
