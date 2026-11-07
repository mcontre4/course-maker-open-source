# Persistent guides

The lesson studio and course syllabus use a conversational Pydantic AI guide. A
question can be answered without changing the outline. An explicit revision request
delegates to the existing lesson/syllabus specialist, validates its structured output,
and saves it with the guide's response.

## Setup

Install the existing AI extra and apply the database migration before starting the API:

```sh
poetry -C backend install --extras ai
cd backend
poetry run alembic upgrade head
```

The guide uses the existing OpenRouter configuration and generation-mode profiles.
Specialist research uses the existing Tavily configuration. No additional memory
library, vector database, or external memory service is required. The repository's
current runtime configuration uses MySQL; the new SQLAlchemy adapters are also tested
against disposable PostgreSQL. This feature does not change database configuration.

## User behavior

- Send successive messages to continue the selected chat. **New chat** starts an
  independent conversation. Chats are saved server-side and can be selected again;
  the selected chat is retained in the page URL.
- Lesson/course outline, script, and animation guide focuses have separate chats.
  They share the same scoped memories and current resource state. The script and
  animation focuses can inspect existing artifacts and refine the outline; media
  generation remains in the existing explicit approval/generation controls.
- **Saved memories** shows user preferences and lesson/course decisions. Users can
  correct or forget them. Forgetting a memory does not erase archived chat messages.
- **Outline versions** displays saved snapshots and offers comparison and restoration.
  Restoration creates another version and resets approval, preserving existing history.
- The first outline-guide chat imports the legacy conversation once. Subsequent chats
  start with empty conversation histories and the applicable shared memories.

Identity uses the existing signed, HTTP-only browser-owner cookie. Memory follows that
identity across resources and reloads, not an account login across devices. A future
authentication adapter can provide the same stable owner ID. Clearing the owner cookie
does not grant access to the prior identity's private chats.

## Persistence and context

`guide_threads` stores resource/owner/guide association and the serialized Pydantic
conversation. `guide_turns` is an append-only transcript with user-visible responses,
native messages/tool results, a revision, and a client request ID. `guide_memories`
stores facts by owner, optional resource, and stable key, with source message and
revision. `outline_versions` stores immutable outline content, its parent revision,
source message, description, and database-generated timestamp.

User memories are available across that owner's resources; lesson/course memories
apply only to the selected resource. Current persisted content takes precedence over
older memories and dialogue. Initial outline generation and downstream script and
animation generation also receive the applicable memory guidance.

Each ordinary request restores the selected native conversation. Once its serialized
history exceeds 100,000 characters, older complete turns are summarized while the
latest eight turns remain verbatim. The conversation ID is preserved. Full transcripts
and tool results remain archived and searchable. This is a context budget, not a claim
that arbitrarily long conversations fit verbatim into a model prompt.

The migration preserves existing current outlines as baselines. Versions overwritten
before the migration cannot be reconstructed from legacy assistant summaries.

## Tools and boundaries

The guide has these explicitly scoped tools:

- `list_outline_versions`, `get_outline_version`, `compare_outline_versions`
- `get_lesson_artifact` (current outline, script, animation, or style)
- `search_lesson_history` (across this owner's chats for the resource)
- `revise_outline`, `restore_outline_version`
- `remember`, `forget_memory`

Tool handlers call application services and repository/agent ports. They cannot choose
another owner or resource. Current context is supplied automatically. Tool execution
is sequential, including when a model requests multiple tools in one response.

Database read boundaries close before model calls. Outline and memory mutations are
staged in the application layer and committed atomically with the response and native
history. A failed model call or failed commit leaves these changes unsaved. Optimistic
chat revisions, resource checks/locks, memory revisions, and database uniqueness
constraints reject competing writes. Reusing a successful message request ID returns
saved history without delegating or writing again. The frontend retains request IDs
after lost responses. External model calls may still incur charges if an attempt fails
before commit.

Standalone outline persistence captures both AI revisions and manual edits in the same
transaction as the content update. Course syllabus specialist outputs are versioned
with their saved curriculum. Version numbers may have gaps because other content
operations also advance resource revisions.

## Verification

```sh
poetry -C backend run pytest tests/unit/courses/guides tests/integration/guides
poetry -C backend run pytest tests/integration/runtime
poetry -C backend run mypy src
poetry -C backend run ruff check src
python backend/scripts/check_hexagonal_boundaries.py --root backend/src
poetry -C backend run tach check
cd frontend
npm test -- --maxWorkers=2
npm run build
```

Backend guide integration tests run the real Pydantic AI tool loop, real FastAPI routes,
production dependency wiring, and real PostgreSQL persistence with a deterministic
model boundary. They cover restored chats across fresh app instances, specialist
delegation, shared-memory boundaries, ownership, retries, manual snapshots,
comparisons/restores, memory correction/deletion, and conversation compaction. Runtime
tests exercise migrations and existing flows on MySQL. Frontend tests cover chat
switching/reopening, lost-response retries, memory controls, version controls, and
archived-message pagination. Live provider quality requires configured provider keys.
