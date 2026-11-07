# Text-to-speech and alignment

Stage 4 of [the generation pipeline](course-generation-pipeline.md) consumes the
saved stage-3 storyboard. It calls **ElevenLabs directly**, with `eleven_v4` and
`POST /v1/text-to-dialogue/with-timestamps`. Audio and original-text character
alignment arrive together; this stage uses neither OpenRouter nor a separate
transcription/forced-alignment model.

## Configuration

Install backend dependencies with `poetry -C backend install`. The optional `ai`
extra is needed for upstream lesson and storyboard generation, not speech.
Add `COURSE_MAKER_ELEVENLABS_API_KEY` to `backend/.env`. Existing OpenRouter and
Tavily credentials remain in use by earlier stages. Never commit `.env`.

The default fallback voice is Eldrin (`6WwXjDDEMyNmFG95zycZ`); override
`COURSE_MAKER_ELEVENLABS_VOICE_ID` to select another voice available to the account.
The [lesson style brief](lesson-style.md) selects a narrator per course or lesson
and supplies expressive delivery separately from the spoken transcript.
V4 settings are `COURSE_MAKER_SPEECH_STABILITY`, `COURSE_MAKER_SPEECH_SIMILARITY`
and `COURSE_MAKER_SPEECH_CLONE_STRENGTH` (defaults 0.5, 0.75 and 0). Clone strength
only affects supported professional clones. Style, speed and speaker-boost fields
from older models are not sent to V4. The model is deliberately pinned to V4.

Default storage is private local files under `backend/.artifacts/speech` when
started from the backend directory. Set `COURSE_MAKER_SPEECH_LOCAL_DIRECTORY` to
an absolute path for a stable location across working directories. This directory
must be on persistent disk; ephemeral container filesystems are unsuitable for
production media.
The Compose setup mounts a named `speech-data` volume at the default container
location and forwards the ElevenLabs credentials/settings. The image creates that
directory for its unprivileged application user; private local artifacts are
excluded from the Docker build context.

For GCS, set `COURSE_MAKER_SPEECH_STORAGE_BACKEND=gcs`,
`COURSE_MAKER_GCS_BUCKET`, `COURSE_MAKER_GCP_PROJECT` and
`COURSE_MAKER_GCS_SIGNER_EMAIL` for the existing asset-signing configuration, then configure Google
Application Default Credentials. GCP storage uses IAM credentials, not an API key.
The existing [Terraform configuration](../infra/terraform/main.tf) already creates
a private versioned bucket, service account, object creator/viewer grants and
keyless signing permissions. Reuse it for audio, transcripts and alignment; no
second bucket or long-lived service-account key is required. A local developer
may authenticate with `gcloud auth application-default login`; production should
use an attached service account or workload identity. See the Terraform variables
for the existing project and globally unique bucket name. Nothing in this change
applies Terraform or creates cloud resources.

## API and artifacts

Authenticated `POST /api/v1/courses/{course_id}/speech/generate` accepts:

```json
{"lessonId": "lesson_<UUID>"}
```

The course must be approved and the selected lesson must have a saved storyboard.
The response is the updated `CourseView`; its lesson has an `alignment` field,
also returned by existing course and lesson GET endpoints. It includes the model,
voice/settings/sample rate, audio object keys, measured scene durations, word
spans, cue IDs with their exact anchors, and scene timeline offsets. HTTP fields
use camelCase; artifact JSON uses snake_case. Narration whitespace is preserved.

Private downloads:

```text
GET /api/v1/courses/{course_id}/lessons/{lesson_id}/speech/audio?scene_id=s01
GET /api/v1/courses/{course_id}/lessons/{lesson_id}/speech/alignment
GET /api/v1/courses/{course_id}/lessons/{lesson_id}/speech/transcript
```

The audio endpoint returns mono 16-bit, 24 kHz WAV. The transcript endpoint returns
the verbatim storyboard narration in scene order, separated by blank lines.
`alignment.json` contains transcripts plus measured word and cue timings. This is
the known narration transcript, not an independent recognition-based assessment
of pronunciation or factual accuracy.

Objects live under
`courses/{course_id}/lessons/{lesson_id}/speech/`: immutable WAVs in `audio/`,
scene checkpoints in `scenes/`, and versioned `alignment.json`/`transcript.txt`.
Only metadata and object keys are stored in the existing course JSON aggregate;
no audio binary or schema migration is needed. Local files are atomically created
with private permissions. GCS writes use generation-zero preconditions. Downloads
require the existing API authorization and return `Cache-Control: private, no-store`.

## Timing, caching and failures

V4 requests stay at or below 2,000 characters. Longer scenes are split at a space
when possible without altering text, then concatenated as PCM with character
times offset by exact sample counts. Each scene is capped at 10,000 characters;
the complete lesson is preflighted against a 100,000-character budget. The approved
narration is never rewritten or shortened.

Duration comes from the audio sample count, never storyboard estimates or the last
timestamp. Word and phrase anchors map to original character spans. V4 can extend
nonspoken terminal punctuation or whitespace beyond the audio end; these spans
are bounded by the measured end only for overruns up to 250 milliseconds. Missing, reordered, truncated or mismatched
alignment, nonfinite times and out-of-audio speech-character timings fail closed.
V4 does not supply a confidence score here; structural validation is not a
statistical confidence estimate or a substitute for listening review.

Cue and word times are relative to their scene. Add `timeline_start_sec` for lesson
times. `COURSE_MAKER_SPEECH_SILENCE_BETWEEN_SCENES_SEC` optionally inserts 0–5
seconds between scenes (default zero). These gaps are represented in the timeline,
not appended to each WAV; the animator must honor the offsets.

Scene hashes cover narration, voice/model/settings and cue identifiers/anchors.
Visual-only edits reuse audio. A failed later scene can resume from completed
checkpoints without billing those scenes again. Checksums protect reuse of WAVs.
Stage retries are explicit; HTTP 429 receives at most two retries with bounded
exponential backoff. Network errors, 5xx and malformed responses stop the stage
because a repeated request could incur another charge. Each request has a
120-second timeout and 10-second connect timeout. Partial chunks within a failed
scene are not checkpointed.

An unchanged saved result is returned without another provider call. Changed
speech settings return 409 rather than silently reusing another configuration.
Lesson-plan, outline and storyboard replacements invalidate saved alignment and
downstream video references. Generation runs outside database transactions; saving
locks and rechecks the course, rejecting concurrent edits. Concurrent generation
requests can still both incur provider charges before the optimistic save check;
callers should serialize jobs per lesson. A distributed job lease, failed-job
ledger, billing totals and object garbage collection remain orchestration work.
Completed checkpoints and unreferenced objects are retained after a failure.

`GenerateSpeech.execute` and `GetSpeechArtifact.execute` are application use cases
with frozen request/response DTOs. Pure domain dataclasses validate speech and cue
invariants. Provider and artifact stores implement inner-layer protocols; all
clients, settings and lifecycles are wired at the composition root. The existing
MySQL course persistence is reused without a database-platform migration.

Missing content/settings conflicts return 409; missing course, lesson or scene
returns 404; bad HTTP input returns 422. Missing credentials, unavailable storage,
provider failures or unusable alignment return 503. Failed generation never marks
the lesson `audio_aligned`.

## Verification

```sh
poetry -C backend run pytest -p no:tach -q
poetry -C backend run ruff check src tests scripts/verify_speech.py
poetry -C backend run mypy
poetry -C backend run python scripts/check_hexagonal_boundaries.py --root src
poetry -C backend run tach check
terraform -chdir=infra/terraform validate
```

Normal tests make no paid calls. They cover domain timing, fake-driven orchestration,
resumption, storage failures, concurrent edits, HTTP provider contracts against a
local server, immutable local filesystem storage, and authenticated HTTP through
the real provider adapter, MySQL, files and fresh application retrieval.

For a paid end-to-end test, run from `backend`:

```sh
PYTHONPATH=src poetry run python scripts/verify_speech.py \
  --env-file .env \
  --course-id course_<UUID> --lesson-id lesson_<UUID> \
  --storyboard /private/path/to/stage3/storyboard.json \
  --output-dir /private/path/to/speech-verification
```

An exported storyboard requires its sibling `lesson-plan.json`; the script imports
both into disposable MySQL/Redis containers without accessing the source database.
Omit `--storyboard` to read an already saved storyboard from the configured database
and copy it into the disposable database. Both modes leave the source unchanged.
The script calls the real ElevenLabs API, verifies audio/transcript/manifest
downloads, persistence and a fresh app's cached POST with the key disabled. It
exports `storyboard.json`, `alignment.json`, `transcript.txt`, scene WAVs, a combined `lesson.wav` for listening and `report.json`.
Reusing an output directory resumes complete scene checkpoints.

GCS uploads and IAM access require a separate live verification once the project,
bucket and credentials are configured. Terraform validation alone does not verify
those permissions.
Switching storage backends does not migrate existing objects. Copy the referenced
objects into the new backend before switching an existing installation.

References: [V4 dialogue API](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue),
[audio with timestamps](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps).

Live verification on October 28, 2026 used the previous stage's exported Newton's
second-law lesson: seven scenes, 831 words and 30 cues. Direct ElevenLabs V4
responses produced 390.64 seconds of measured audio, versus a 300-second storyboard
planning estimate. Narration and cue anchors were preserved. Local WAVs, transcript,
alignment, real MySQL round-trip, authenticated downloads and a fresh application
with the ElevenLabs key disabled all passed. Validation also caught V4's terminal
punctuation timing beyond the audio boundary and floating-point offset changes
across MySQL JSON persistence; both have regression coverage. GCS remains untested.
