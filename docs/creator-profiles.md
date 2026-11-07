# Creator profiles and public videos

Creator profiles use the existing server-signed browser identity (`course_maker_owner`).
They live in the courses bounded context because registered-user authentication is
not connected to lesson ownership yet. Names and raster avatars are persisted in
`creator_profiles`; email remains browser-only. Settings explicitly saves the
public name/photo, and the account menu links to the public profile.

Apply the database migration before running the updated API:

```sh
poetry -C backend run alembic upgrade head
```

New courses persist their creator ID in the existing aggregate JSON. Standalone
lessons already persist an owner ID. Historical courses without an owner retain
unknown attribution; no user is assigned ownership by guesswork.

## Publication and browsing

A lesson with a `video_url` or `video_asset_id` is public automatically. Animation
source (`animation_ready`) alone does not qualify. Profiles list standalone videos
and courses containing at least one finished video, with only their finished
lessons. All course lessons are evaluated individually, even before the full
course has finished generating.

- `/creators/:creatorId`: public profile and published lessons/courses.
- `/watch/lessons/:lessonId?course=:courseId`: read-only public video playback.
- `GET /api/v1/creators/me`: current identity, initializing an empty public profile.
- `PUT /api/v1/creators/me`: update only the current signed identity's name/photo.
- `GET /api/v1/creators/:creatorId`: public profile projection.
- `GET /api/v1/published/lessons/:lessonId?course_id=:courseId`: public playback projection.

Public responses omit prompts, chat turns, plans, provider usage, private email,
quiz answers and source/artifact keys. Draft playback returns 404. Public watching
uses a separate route from generation/editing, and does not update a creator's
learning progress.

Video assets reuse the existing Storage port and GCS adapter. A course asset is
resolved from `courses/<course-id>/<asset-id>`, with a fresh 15-minute signed URL.
Database work ends before contacting storage. Direct video URLs are used as saved.

## Storage verification

The observations below describe the original creator-profile implementation.
The current [Canvas pipeline](canvas-video-production.md) renders and validates MP4s
for local playback before delivering new animations.

At implementation time, the running local API had 13 course lessons and 5
standalone lessons, including 2 animation-source references, but no video URLs or
video asset references. GCS was disabled and speech used local storage. The
animator generates/statically validates Remotion source; `Course.animate_lesson`
clears video references. Speech has a separate GCS artifact adapter.

A rendered MP4 existed under the primary checkout's local `.playback` artifacts,
but was not referenced by those lesson records. This feature consumes finished
videos; it does not add a rendering/upload stage to the animator pipeline.

## Verification

- Unit tests cover identity validation, save/reload, unknown/empty profiles,
  creator isolation, publication filtering, draft denial, direct URLs, legacy
  ownerless courses and storage resolution outside a transaction.
- The HTTP integration test uses disposable PostgreSQL, the real profile
  migration, production dependency wiring, separate creator/viewer cookies,
  persisted standalone/course content, and an injected media-storage boundary.
- React tests exercise profile → lesson → creator navigation, starting a course,
  private-email separation, profile updates and missing-profile recovery.
- Browser verification used the real API and disposable PostgreSQL. A short clip
  from the existing rendered MP4 decoded and played (readyState 4, advancing
  playback time); starting a course and switching published lessons also worked.

Live GCS upload/download was not exercised because the tested local API had no
configured GCS bucket. The application-to-Storage boundary was verified with the
existing course asset key format and an injected local media implementation.
