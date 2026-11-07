# Generation activity across refreshes

Generation activity is shared through Redis, rather than inferred only from a browser mutation. Authenticated routes for existing courses and lessons coordinate writes with a resource-wide lease. A conflicting write returns HTTP 409 before invoking a use case. The lease renews while the request runs and is released on completion or failure; abandoned leases expire after 60 seconds.

Successful reads return `X-Active-Operation` and `X-Operation-Error` headers with `Cache-Control: no-store`. HTTP adapters translate these into application read models. Course and standalone lesson pages poll every two seconds, display **In Progress**, and disable conflicting actions until the server reports completion. A failed step leaves a retry notice available after refresh. The next write clears that notice. If status polling fails, the page shows the read error and a retry action instead of presenting stale progress or generation controls. The hidden workspace retains unsaved edits and chat drafts until reads recover. Activity headers are exposed to browsers through CORS.

Video generation uses one server request, so refreshing cannot interrupt the browser between pipeline stages:

- `POST /api/v1/lessons/{lesson_id}/video`: approval, storyboard, speech, animation. Accepts `expectedRevision` and `generationMode`.
- `POST /api/v1/courses/{course_id}/video/generate`: lesson outline, storyboard, speech, animation. Accepts `lessonId` and `generationMode`.

The application orchestrators reuse the existing stage use cases and their saved artifacts. Each stage retains its own short transaction, revision checks, provider ports, and spend tracking. No transaction spans the entire pipeline or provider calls. Individual stage endpoints remain supported.

## Verification

Regression tests cover fresh page mounts during outline/video generation, polling to completion, disabled controls, saved failure notices, HTTP header mapping, complete server pipelines, mode propagation, revision handling, Redis duplicate rejection, lease renewal, and token-safe cleanup and failure recording. Starting a new lease also clears the old failure notice atomically.

Manual browser checks used Fast mode with a one-minute water-cycle lesson and a one-hour weather course. Refreshing during video and syllabus generation restored **In Progress** and disabled conflicting actions. The syllabus subsequently appeared automatically with five lessons and enabled approval. A duplicate request during video generation returned HTTP 409 without starting another generation. The animator completed in Fast mode with validated source saved as `animation_ready`; a subsequent authenticated read returned HTTP 200 with no active operation. Thumbnail regeneration and a Fast-mode style update also completed across refreshes.

Local verification records:

- Lesson: `lesson_0e5b1281-f8be-4390-b081-a89b3a740b64`.
- Course: `course_57056bc8-6a4f-4ea7-bcb9-79db6e89b2c3`.
