# SVG thumbnails

Thumbnails follow the video's selected visual style, including its palette, shapes,
line treatment and surface character. Course lessons use their own style override
or inherit the course style. With no saved style, Flat-Vector Science is used.
Subject matter comes from the saved title, description and lesson topics.

The default is **`openai/gpt-6.1-sol` through OpenRouter**, with medium reasoning.
This is one text-completion request producing SVG source; no image model or agent
loop is involved. Set `COURSE_MAKER_THUMBNAIL_MODEL` to change this independently
of the lesson's Fast/Balanced/Pro generation setting. It reuses
`COURSE_MAKER_OPENROUTER_API_KEY`. Both native startup and Compose support it.

The system prompt is `backend/src/app/courses/adapters/ai/thumbnail_prompt.md`.
The three approved examples in its `thumbnail_examples/` sibling directory are
included as composition and SVG structure references on every call; the selected
video style takes precedence over their appearance. They are packaged backend resources;
generation does not depend on the frontend checkout being available.

## Lifecycle

- Saving a new course commits and returns the draft immediately, then queues its
  thumbnail in a dedicated worker pool with a separate database session.
- Saving a standalone lesson returns its draft immediately, without calling AI.
  Starting its outline queues the thumbnail alongside style and outline planning.
  Neither the outline nor subsequent script/video stages wait for the thumbnail.
- A course lesson queues a thumbnail when its teaching plan is generated.
- Thumbnail requests have their own Redis lease, independent of generation and
  style changes. `X-Thumbnail-Operation` exposes their status after a refresh;
  `X-Active-Operation` tracks the main generation separately.
- Missing credentials or provider/validation failure leave the saved draft intact.
  The UI offers **Generate thumbnail** to retry. Existing thumbnails remain visible
  during regeneration or a failed attempt.
- **Regenerate thumbnail** uses the latest saved subject and visual style. Save unsaved details
  first. Thumbnail generation can run alongside the other agents.
- Existing images are reused unless regeneration is explicit. Details edits retain
  existing artwork; regenerate it after changing the subject if needed.
- Thumbnail saves re-read and lock the aggregate, reject changes to the subject, style or
  image, and merge onto the latest teaching content. Other generation stages retain
  thumbnails saved concurrently. Image-only updates do not advance the standalone
  content revision. Standalone generation checks ownership before calling the provider.
- Provider usage is recorded under the `thumbnail` stage in the existing spend
  ledger. Drafts must exist before provider instrumentation records its first charge.

## Cancelling generation

While an outline, script, or video is running, the studio exposes a cancel button.
Authenticated POST `/api/v1/lessons/{lesson_id}/generation/cancel` (with the signed
owner cookie) or `/api/v1/courses/{course_id}/generation/cancel` requests a stop.
Script preparation uses one POST `/api/v1/lessons/{lesson_id}/script/generate`
for approval and script generation, so cancellation covers the entire operation.
The activity lease remains held until the worker acknowledges cancellation, and
polling reports `cancelling/<operation>` meanwhile. Each generation transaction
checks the request token before starting and committing, so an in-flight provider
result is discarded and later stages do not start. Completed stages remain saved.
A provider request already in flight can finish before cancellation is acknowledged.
Thumbnail work continues independently.

## API and storage

Authenticated POST endpoints, with JSON `{ "regenerate": false }` by default:

- `/api/v1/lessons/{lesson_id}/thumbnail`
- `/api/v1/courses/{course_id}/thumbnail`
- `/api/v1/courses/{course_id}/lessons/{lesson_id}/thumbnail`

The lesson route also requires the existing signed owner cookie. Successful
responses use the existing standalone/course response DTOs. Failures return 503,
concurrent edits 409 and inaccessible standalone lessons 404.

The adapter validates a 640×400 viewBox, document/element size limits, shape and
attribute allowlists, local references and explicit hex colors appropriate to the style. It rejects
scripts, event handlers, CSS, links, embedded images/HTML, entities and external
resources. Harmless XML declarations and comments are normalized away. Truncated
provider responses are rejected. The serialized SVG is base64-encoded into the
existing `image` field and stored in the existing JSON payload; no migration or
new storage service is required. The frontend displays it with `<img>`, never
inline HTML. Broken images fall back to the existing illustration.

This keeps initial integration small. Images are currently included in list DTOs;
if catalog payload size becomes material, move the same validated SVG to asset
storage and return its image URL instead.

## Verification

From the repository root:

```sh
poetry -C backend run pytest tests/unit/courses tests/integration/thumbnails tests/integration/runtime/test_generation_cancellation.py -q
poetry -C backend run mypy
poetry -C backend run ruff check src tests/integration/thumbnails
poetry -C backend run python scripts/check_hexagonal_boundaries.py --root src
poetry -C backend run tach check
```

The thumbnail integration scope uses a disposable PostgreSQL container and a real
local HTTP provider to exercise create → generate → persist → reload → reuse →
regenerate, including the spend ledger foreign key. No paid requests are made by
automated tests. Frontend tests cover preview rendering, regeneration and errors.

For a live check, open **New lesson**, select **Fast**, enter a title and description,
and **Build my lesson outline**. Confirm the studio opens immediately with loading
indicators, then the thumbnail and outline appear. Regenerate the thumbnail, reload, and find it in
**My creations**. This creates a real draft and incurs the configured model's token
charges. Fast applies to subsequent lesson generation; thumbnail selection stays
independent.
