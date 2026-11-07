# Code Navigation

- Always use Serena MCP for code navigation, symbol lookup, reference tracing, and project searches. Use shell tools only when Serena is not suitable, such as for non-code files or generated assets.

# Technology Stack

- FastAPI for the HTTP API.
- PostgreSQL for persistent relational data.
- SQLAlchemy for database access and persistence adapters.
- Redis for caching, transient state, and asynchronous coordination where needed.
- Poetry for Python package and dependency management.
- mypy for static type checking.
- Ruff for Python linting and import sorting.
- LangChain and LangGraph for LLM and agent workflows.

# Backend Architecture

The backend uses **hexagonal architecture** (ports and adapters). Organize code around the business domain and use cases, not around framework or infrastructure concerns.

## Layers and responsibilities

- **Domain** contains the business model and business rules. Group domain code by domain (for example, `users`, `orders`, or `cores`). Domain code must be independent of HTTP, databases, ORM models, queues, and other external libraries.
- **Domain services** implement domain-specific business logic that does not naturally belong to a single entity or value object. They belong to a domain, such as `users`, `orders`, or `cores`.
- **Application services** implement one use case each, such as `create user` or `get user`. They coordinate domain objects, domain services, repositories, and transactional boundaries; they should contain orchestration and authorization decisions, not core business rules.
- **Repositories** are domain-specific ports for loading and persisting aggregates. Define their interfaces alongside the domain or application layer that consumes them, using domain types rather than persistence or ORM types.
- **Adapters** implement ports at the system boundary. Examples include database/ORM repository implementations, HTTP controllers, message consumers/producers, external API clients, and framework wiring.

## Dependency direction

Dependencies must point inward:

`adapters -> application services -> domain`

- The domain must not import application services or adapters.
- Incoming adapters call application services only; they do not invoke domain services directly.
- Application services coordinate domain entities and domain services, repository ports, and transaction-boundary ports. They must not call concrete adapters, ORM models, HTTP clients, or other infrastructure directly.
- Domain services must not call collaborators or fetch dependencies. They operate solely on the entities, value objects, and primitive data supplied as arguments by their caller—normally an application service.
- Domain models must not call repositories, services, adapters, or infrastructure. Any operation that requires loading, querying, or persisting data belongs in an application service.
- Application services depend on repository and transaction-boundary *interfaces* (ports), never concrete database, HTTP, or third-party clients.
- Composition/wiring happens at the edge of the application: inject adapter implementations into application services there.
- Incoming adapters translate transport input into use-case input and translate use-case results/errors into transport responses. They must not contain business logic.
- Outgoing adapters translate between domain models and external representations. Keep ORM/database records and API DTOs out of the domain.

## Design rules

- Prefer a feature/domain-oriented structure over a global `controllers`, `services`, and `repositories` structure.
- Name application services after their use case (for example, `CreateUser` or `GetUser`); name domain services and repositories after their domain.
- Model failures explicitly with domain/application errors; adapters map them to protocol-specific responses (such as HTTP status codes).
- Keep transaction management in the application layer or its boundary, never in domain entities or domain services.
- Do not let framework decorators, request/response objects, ORM entities, or database queries leak past adapters.

## Use case boundaries (Clean Architecture — Use Case Interactors)

- Each application service is one use case interactor with **a single public method** `execute(...)`. No `UserService` with multiple operations; split into `CreateUser`, `GetUser`, etc.
- Define explicit **Input and Output DTOs** owned by the inner layer (`application` or `ports`): `CreateUserRequest` / `CreateUserResponse` as frozen dataclasses. Adapters translate `HTTP/Pydantic -> Request` and `Response -> HTTP`.
- Never expose domain entities directly to adapters. The use case returns a `Response` DTO; the adapter maps to its own view model. This keeps `Framework -> Adapter -> Application -> Domain` stable and prevents accidental domain leakage.
- Validate at the boundary: incoming adapters validate transport input (Pydantic, schema) before calling the use case; domain invariants are enforced inside entities/value objects.

## Cross-cutting ports — time, identity, and randomness (Dependency Inversion)

- Treat `clock`, `ID generation`, `random` and other volatile details as **ports owned by the inner layer**. Define `Clock` and `IdGenerator` as `Protocol` in `app/shared/domain` or `app/<domain>/ports`.
- `domain` and `application` must never call `uuid4()`, `datetime.now()`, `time.time()` or `random` directly. Inject the port and let `shared/infrastructure` adapters (`SystemClock`, `UuidIdGenerator`) provide the implementation.
- Composition root wires the concrete adapter; tests inject deterministic fakes (`FakeClock`, `FakeIdGenerator`) for repeatable assertions.

## Domain purity and invariants

- `app/<domain>/domain` and `app/shared/domain` contain only pure business logic: frozen dataclasses, value objects, and domain services operating on arguments.
- Entities/value objects enforce invariants in `__post_init__`/`__init__` and expose behavior, not setters. No anemic models.
- Domain must not import `application`, `adapters`, `sqlalchemy`, `fastapi`, `redis`, or any infrastructure. Domain services must not fetch dependencies — they receive entities/value objects as arguments from the application service.

## Cross-domain independence (Stable Dependencies Principle)

- `app/<domain>.*` must not import `app/<other_domain>.*`. Domains are independent bounded contexts. Share only via `app/shared/*` or via asynchronous domain events/outbox.
- `tach` and the boundary checker enforce this: each domain's `depends_on` lists `shared` plus its own slices only. Adding a domain requires copying the `app.users.*` block.

## Composition root isolation

- Only `app/main.py` and `app/<domain>/composition.py` may construct infrastructure: `Engine`, `Session`, `Redis`, `Settings`, framework clients. All other layers receive **value objects or ports** via DI.
- `application` and `domain` receive validated config, not `os.getenv()`; `adapters` receive a `Session`/`Client` already bound to the current operation scope (one session per `UnitOfWork`).

## Dependency injection

- Prefer dependency injection over global access or constructing dependencies inside domain and application services.
- Inject repository and external-service ports into application services; inject adapter implementations only in the composition root.
- Tests must replace dependencies through injection rather than mutating global state.

## Singleton classes

- Use singleton classes only for stateless, process-wide infrastructure dependencies that are expensive or unsafe to create repeatedly.
- Suitable examples include a database connection pool, validated configuration provider, logger, metrics/tracing client, or pooled HTTP client.
- Do not use singletons for domain entities, domain services, application services, repositories, request context, authenticated-user state, or mutable caches.
- A singleton must have controlled initialization, a narrow interface, and safe concurrent use.

## Shared infrastructure lifecycle

- Create and validate shared infrastructure at application startup in the composition root; fail fast when configuration is invalid.
- Pass shared infrastructure to adapters and application services through dependency injection. Domain code must not access it directly.

## Database sessions

- Treat database sessions, ORM clients, and transaction handles as adapter implementation details; never expose them in domain or repository-port interfaces.
- Scope database sessions to an operation. Do not make them process-wide singletons.

## Transactions

- Application services define transaction boundaries: use one short-lived transaction per write use case when its changes must succeed or fail together.
- The persistence adapter starts, commits, and rolls back the concrete transaction. Domain code must not manage transactions directly.
- Do not keep transactions open during external API calls, slow computation, or user interaction.
- Read-only use cases should avoid explicit transactions unless a consistent snapshot across multiple reads is required.

## Unit of work

- Use an application-layer unit-of-work port when a use case needs multiple repositories to share one transaction.
- Keep unit-of-work ports and implementations transaction-only: they own commit, rollback, and lifecycle, but do not depend on or expose repositories.
- Inject repository ports directly into application services. At the composition root, wire repositories and the unit of work to the same transaction-scoped session.
- The unit of work commits only after the use case succeeds; it rolls back on failure.
- Keep ORM and database transaction types inside the unit-of-work adapter.

## External side effects

- Do not send emails, call third-party APIs, or publish non-transactional messages while a database transaction is open.
- Use a transactional outbox when domain changes and event publication must be reliable: persist the state change and outbox record atomically, then publish asynchronously with retries and idempotency.

## Database errors and retries

- Map expected persistence failures to application/domain errors; incoming adapters map those errors to protocol-specific responses.
- Retry transient database failures only when the use case is safe to retry. Write use cases must be idempotent where retries are possible.
- Enforce essential invariants with database constraints as well as application-level checks.

## Testing rules

- Unit-test domain entities and domain services without infrastructure dependencies.
- Unit-test application services with in-memory or fake implementations of repository and external-service ports.
- Monkey patching is forbidden. Replace dependencies through injection with explicit fakes instead.
- Test adapters separately with integration tests against their real dependencies, such as the database, HTTP transport, message broker, or third-party API sandbox.
- Use adapter tests to verify mapping at boundaries: domain models to persistence records, transport input to use-case input, and domain/application errors to protocol-specific responses.
- Keep tests focused on the layer under test; do not require a running database or HTTP server to test domain or application behavior.
- Organize pytest fixtures in `conftest.py` files by scope. A fixture is available to tests in its directory and descendants only.
- Place a shared fixture in the nearest common ancestor of every test that needs it; never import fixtures from a sibling `conftest.py`.
- Keep `tests/conftest.py` and `tests/integration/conftest.py` minimal. Put a concrete infrastructure fixture at the nearest common ancestor of the tests that use it; do not make it autouse outside that dependency's specific test scope. Keep reusable fakes and factories in `tests/fakes/` or `tests/fixtures/`.

## Dependency enforcement

Enforced at pre-commit and in CI. Both gates must pass; do not bypass them.

- **Role-based script (auto-discovered, no per-domain update):** `backend/scripts/check_hexagonal_boundaries.py` (alias `backend/script/check_exagon_handlers.py`) — run as `python backend/scripts/check_hexagonal_boundaries.py --root backend/src`. It derives the role from the path (`app/shared/domain`, `app/<domain>/domain|ports|application|adapters`, `app/main`/`app/<domain>/composition`) and enforces `adapters -> application -> domain` plus infra-leak checks (`sqlalchemy`/`fastapi`/`redis` forbidden in `domain`/`ports`/`application`), single-public-method per use case, `Request/Response` DTO boundaries, `Clock`/`IdGenerator` ports instead of direct `uuid`/`datetime` calls, and cross-domain isolation. New domains under `src/app/<domain>/` are covered automatically.
- **Import graph (`tach`):** `backend/tach.toml` (`source_roots: src`, `exact: false`). `tach check` enforces the same direction as an explicit module graph with cross-domain isolation. **When you add a new domain**, you must update `backend/tach.toml`: copy the `app.users.*` block for `app.<new_domain>.*` (domain → ports → application → adapters → composition) and add its `adapters` to `app.main.depends_on`. Run `poetry -C backend run tach mod` to auto-discover, or edit manually using the commented template at the bottom of the file. Then run `poetry -C backend run tach check` locally. After adding `tach` to `backend/pyproject.toml`, run `poetry lock` locally (requires network) and commit the updated `poetry.lock`.
- Pre-commit hooks (`backend-hexagonal-boundaries` + `backend-tach` + `backend-mypy` + `backend-ruff`) are `always_run: true` in `.pre-commit-config.yaml` and must stay that way.

## Repository conventions

- Define repository ports as `typing.Protocol` types in each domain's `ports/` package.
- Use `get_by_<field>() -> Entity | None` for optional lookups.
- Use `require_by_<field>() -> Entity` when absence is an application or domain error.
- Use `add(entity)` for newly created aggregates; do not use `create`.
- Use type-prefixed IDs for persisted aggregates exposed outside the domain (for example,
  `user_<UUID>`). Model them as domain value objects and persist the complete prefixed string.
- Do not expose ORM records, sessions, or transaction details through repository ports.
- Add query methods only when required by a use case; avoid generic CRUD repositories.
