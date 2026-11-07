# Standalone lessons

Users can create a lesson at `/lessons/new` with a title, description, and integer
video duration from 1 to 10 minutes. The lesson studio at `/lessons/:lessonId`
starts with the existing Lesson Creator agent, supports outline revisions through
chat and direct editing, and requires approval before creating media. The home page
includes saved lessons and lesson ideas above the existing course recommendations.
Explore is unchanged.

## Persistence and ownership

Apply `poetry -C backend run alembic upgrade head` before starting the updated API.
Migration `0003` creates `standalone_lessons`, with a prefixed lesson ID, indexed
owner ID, database duration constraint, and aggregate payload. There is no course
foreign key and standalone lessons do not appear in course lists.

The current application has no account sign-in or authenticated user session.
Ownership therefore uses a persistent, HttpOnly, SameSite cookie signed by the
server's API key. It is Secure over HTTPS. Ownership is never accepted from request
bodies or unsigned headers. All reads, revisions, approval, and media operations
check the owner; another owner receives 404. Clearing the cookie loses access to
that browser's lessons. Replace `get_owner` with an account-session adapter when
sign-in is introduced; existing browser owners will need an explicit account-linking
migration. Changing the signing key invalidates browser identities.

These lessons are private drafts owned by the browser identity. Recommendations
are clearly presented as ideas to create, rather than other users' private lessons.

## Copying lessons

Use **Copy lesson** in the lesson studio or on a public lesson's watch page.
A sheet shows the source thumbnail (carried over unchanged; regenerate it in the
copy) and a title field pre-filled with the source title plus `-copy`. Choose
**Create copy** to open the copy in the studio for editing. The copy belongs to the
browser identity performing the copy and has a new lesson ID. Default titles are
shortened as needed to stay within 120 characters.

Owners can copy their lesson's saved state at any stage. Other users can copy only
the finished version; private draft changes and version history are excluded.
Copies retain saved content and generation preferences, with all embedded lesson
IDs and interactive plan hashes updated. Editing or generating the copy leaves the
source unchanged. Chat history and spend records start fresh.

`POST /api/v1/lessons/{id}/copy` accepts `{}` for a standalone source or
`{courseId}` for a course lesson, plus an optional `title` (1-120 characters,
trimmed) that names the copy and its earlier playable versions; without it the
title ends in `-copy`. A blank or overlong title is rejected. It returns the new standalone lesson with status
201. Course copies inherit the course's style where needed and use the standalone
studio's duration limits. A missing lesson or another user's unfinished lesson
returns 404. Ownership always comes from the server's identity dependency.

The browser copy tests run against disposable PostgreSQL with deterministic
generation ports. They cover ownership, draft denial, independent generation,
editing, regenerated video playback, persistence, and reload.

## Architecture and pipeline

`courses/domain/standalone.py` owns the independent aggregate. It reuses the
existing lesson, plan, storyboard, alignment, and animation values inside the same
bounded context. Repository ports use domain types; application use cases expose
only `execute` with frozen request/response DTOs; HTTP and SQLAlchemy remain in
adapters. Wiring is in `courses/composition.py`.

The original LessonAgent port accepts optional description, previous-plan,
conversation, and revision-message context. Existing course calls keep their
original behavior. A standalone brief supplies the title as its broad concept and
objective; the agent can revise individual teaching beats and examples. Every
successful turn and its outline are saved. Plan edits invalidate approval,
storyboard, narration, and animation together.

The studio's **Edit outline** action edits the saved plan directly: objectives,
ordered teaching beats and timing, teaching notes, understanding checks, worked
examples, knowledge, facts and scope. **Save outline** validates and persists those
edits without calling the Lesson Creator or adding an AI conversation turn. It
retains researched sources, the lesson identity and authored text formatting. Unchanged saves preserve
approval and generated media. Failed saves keep the editor's unsaved text for
retry; stale revisions cannot overwrite a newer plan.

After saving, **Approve & generate video** passes that exact saved plan to the
Script & Storyboard Agent, followed by narration and animation. Fast/Balanced/Pro
applies to the subsequent generation. Chat remains the explicit way to ask AI to
revise the outline; it receives the latest manually edited plan and objectives.
Save or cancel direct edits before using chat, changing style or generating media.

Approval runs the same StoryboardAgent, SpeechSynthesizer, checkpointed speech
pipeline, and Animator used by courses. Each stage saves independently; retrying
uses the saved artifacts. External calls happen outside database transactions.
A row lock and revision recheck protect the final save from concurrent edits.
Provider failures preserve the last successful stage. Requests are not automatically
retried after an ambiguous network failure: reload to inspect the saved stage.

The animator now creates plain-JavaScript Canvas source and delivers a fully rendered,
validated MP4 for in-app playback. A required visual style supplies executable
references. The user can enable independent AI review or review the finished video
themselves; the latter is explicitly marked as skipped review. See
[JavaScript video production](canvas-video-production.md) for rendering and repair.
The duration picker, domain, and database cap requested duration at 10 minutes;
the standalone domain also rejects outlines, estimated scripts, and measured
narration that exceed 600 seconds.

## API

All routes require the existing API bearer authentication and same-origin owner
cookie. The Vite development proxy supplies the bearer key server-side. Production
must retain a same-origin authenticated proxy and forward cookies and Set-Cookie.
Long-running media requests need a suitable upstream timeout (development allows
20 minutes; the animator has its own configured timeout).

- `POST /api/v1/lessons`: `{title, description, minutes, style: {visualStyleId: "flat-vector-science", reviewOutput: true}}`; returns a saved draft.
- `GET /api/v1/lessons?limit=100&offset=0`: the current owner's saved lessons.
- `GET /api/v1/lessons/{id}`: saved content, revision, approval, and chat turns.
- `POST /api/v1/lessons/{id}/plan`: `{message, expectedRevision}`.
- `PUT /api/v1/lessons/{id}/outline`: `{expectedRevision, outline}`; saves manual
  edits without generation. `outline` contains the editable lesson-plan fields,
  excluding the server-owned `lessonId` and research `sources`. Invalid content or
  timing returns 422; stale revisions return 409. Timing must fit the requested
  duration within 30 seconds and never exceed 600 seconds.
- `POST /api/v1/lessons/{id}/approve`: `{expectedRevision}`.
- `POST /api/v1/lessons/{id}/storyboard`: `{expectedRevision}`.
- `POST /api/v1/lessons/{id}/speech`: `{expectedRevision}`.
- `POST /api/v1/lessons/{id}/animation`: `{expectedRevision}`.

Mutations return the latest lesson view. Pass its revision to the next operation.
Stale revisions return 409. The browser keeps the same saved lesson after a
planning error and retains unsent chat text on failure. Standalone generation
requires API mode; the legacy local demo does not simulate AI generation.

## Verification

Focused unit tests cover the full three-minute pipeline using explicit port
fakes, owner isolation, stale revisions, provider failure, concurrent saves,
regeneration invalidation, and duration constraints. Runtime integration tests
use migrated disposable MySQL, verifying HTTP validation, persistent ownership,
forged-cookie rejection, and saved-draft recovery. Existing course speech tests
exercise the shared extracted speech pipeline. UI tests exercise creation,
StrictMode's single initial generation, chat, pipeline progress, restoration,
duration selection, and home-page ordering.

## Live verification (2026-10-29)

A real three-minute chemistry lesson, “Why atoms form bonds,” was created through
the browser against an isolated migrated MySQL database. OpenRouter and Tavily
produced the outline; a chat message replaced the final energy-release section
with an electron-sharing recap while preserving the water example and 180-second
budget. Approval and the full storyboard/script were saved, and a browser reload
after an API restart restored the lesson, conversation, and script.

The initial narration run hit the API key’s credit quota (`quota_exceeded`, HTTP
401). Raising the key-specific quota allowed narration to complete from the saved
script. Animation generation then resumed from the persisted measured audio.
Automated fake-driven tests cover both stages, including partial-audio checkpoint
recovery. The adapter maps the recognized quota code to safe, actionable feedback
without exposing provider response bodies.

The final live run completed narration and animation: four audio scenes totaling
180.4 seconds, four animation scenes, and 21 cue events. The main-checkout UI
restored the saved animation-ready result after reloading. Durable source
verification also passed with the provider key disabled, without another paid run.

Offline visual QA found that the verification image lacked a font supporting the
subscript in H₂O. The verification Dockerfile now installs DejaVu core fonts as a
fallback. Re-rendered water and recap frames display the formula correctly;
charge, energy, water, and recap layouts were visually inspected. Repeated-seek
and cue/scene-boundary frame checks passed with the generated source unchanged.
The integrated main checkout passed all 80 frontend tests and its production
build; all backend commit hooks, including the 95% coverage gate and both
architecture gates, passed.

## Direct outline editing verification (2026-10-29)

The real browser flow ran against an isolated migrated database with Fast selected.
For “Why a rainbow forms,” the browser generated an outline, edited its objective,
first teaching-beat title and teaching notes, rejected an invalid timing total,
saved the corrected outline and restored those exact edits after a reload.
Approval then completed scripting, narration and validated animation source.
A second reload restored the completed lesson with Fast still selected.

The persisted lesson reached revision 6 with four scenes and 92.08 seconds of
measured narration. Both scripting and animation used `openai/gpt-6-luna`.
The animator's exported lesson-plan input matched every field of the saved edited
plan. There was exactly one successful planning request and one conversation turn:
manual edits and approval did not rerun the Lesson Creator. The script reflected
the manually added “team of colors” explanation.

All 468 backend tests and 119 frontend tests passed. The unit coverage gate reached
97.32%; Ruff, mypy, Tach, both architecture checks, formatting and the production
frontend build passed. Automated coverage includes exact saved-content handoff,
approval/media invalidation, no-op saves, timing and content validation, stale
revisions, ownership, save failure/retry/cancel, adding/reordering/removing beats,
editing examples, and optional subsequent AI revision from the edited plan.

Local screenshots, the verification summary and generated source are preserved
under `backend/.artifacts/outline-verification/`. This verifies the supported
pipeline through animation source; the application still does not render video.
