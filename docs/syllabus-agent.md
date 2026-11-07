# Syllabus agent

The complete pipeline and stage ownership are described in
[course-generation-pipeline.md](course-generation-pipeline.md).

**Pydantic AI is the agent harness for Course Maker agents.** Keep framework,
model-provider, and tool integrations in outgoing adapters behind inner-layer
ports. The syllabus agent uses OpenRouter's Responses API with
the selected [generation profile](lesson-creator-agent.md) and Pydantic AI's Tavily search tool. It may search when needed,
ask clarifications, generate a syllabus, and revise it in subsequent requests.

Its versioned [system prompt](../backend/src/app/courses/adapters/ai/syllabus_prompt.md)
implements this README's conversational experience and the pipeline's curriculum
rules. Edit that prompt deliberately when changing agent instructions; the agent
does not load arbitrary README text at runtime.

### Local setup

Run backend commands from `backend/` (or use `poetry -C backend`).

```sh
cp -n .env.example .env
poetry install --extras ai
# Fill in backend/.env using backend/.env.example as a reference:
# COURSE_MAKER_OPENROUTER_API_KEY=...
# COURSE_MAKER_TAVILY_API_KEY=...
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

`backend/.env.example` documents the required database, API authentication, and
provider settings. Keep real keys in the ignored `backend/.env`. Missing provider
keys leave the rest of the API usable; generation returns HTTP 503. Restart after
changing credentials. The existing MySQL persistence and migration setup is used.

### Generate and refine a syllabus

First create a draft through `POST /api/v1/courses`, including its learning-time
budget. Then send the user's message verbatim in the generation request:

```http
POST /api/v1/courses/{course_id}/syllabus/generate
Authorization: Bearer <COURSE_MAKER_API_KEY>
Content-Type: application/json

{"message": "Teach beginner Python and include a small final project.", "expectedRevision": 0, "generationMode": "balanced"}
```

The response contains `course`, the agent's `message`, and `session` with
`sessionId`, `revision`, conversation `turns`, and a structured `curriculum`.
The curriculum contains the course guide, objectives, prerequisite IDs, week
assignments, separate learning-time allocations, topic coverage, and warnings.
Chapter and lesson IDs are assigned by the application and preserved on revisions.
Clarification replies keep the saved syllabus unchanged.

Send subsequent messages to **the same endpoint with the same course ID** and the
latest `expectedRevision`. For example:

```json
{"message": "Add more file handling examples and make the final project smaller.", "expectedRevision": 1}
```

`GET /api/v1/courses/{course_id}/syllabus/session` restores the conversation and
latest curriculum without calling the model. One durable session belongs to each
course. Full Pydantic AI conversation state, including tool calls/results, lives
in `syllabus_conversations`; each run reloads it, including across restarts or
workers. Model memory does not depend on keeping a process or connection alive.
The latest saved course is supplied separately so manual edits take precedence
over historical model outputs. Raw provider history is never returned by the API.

Provider clients are scoped to one turn and closed on the same event loop that
uses them. Typed request/response DTOs cross application boundaries; JSON and
framework-specific history serialization stay in adapters.

Successful turns and syllabus updates commit atomically after generation finishes.
Concurrent changes return HTTP 409; reload before retrying. `expectedRevision` is
optional for compatibility, but clients should send it to reject stale messages
before model execution. Automatic retries of the entire endpoint are not safe:
reload the session after an ambiguous response before resubmitting a message.
The write boundary serializes competing course changes, including clarification
turns. Teaching changes invalidate affected lesson videos and quizzes; scheduling
changes preserve media. Approved courses remain protected from edits. Deleting a course deletes its
conversation. The existing `/chat` endpoint remains reserved for tutor chat.

Research is limited to five results per Tavily search, six tool calls and twelve
model requests per turn, with a 120-second turn timeout and a token budget. All
searches run sequentially; once the search allowance is used, the tool is hidden
so the agent can finish from its existing evidence. Generated curricula must
include every requested week, a topic-coverage report, and a usable course guide.
All conversation history is retained; exceeding a limit fails the turn rather than
silently dropping memory. Provider/tool failures return HTTP 503 and leave the
last saved syllabus intact. Run an opt-in live smoke test when changing model or
provider integrations; the ordinary test suite explicitly disables live credentials.

Run `poetry run pytest` for tests against deterministic agent/search doubles and
disposable databases/Redis (Docker required); no live AI keys are needed. Unit
tests exercise domain rules and application ports, while adapter tests exercise
the Pydantic AI tool loop, serialized context recovery, HTTP mapping, migrations,
and transaction behavior.
