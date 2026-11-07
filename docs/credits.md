# Credits and Stripe Checkout

Apply migration `0015` before starting the API:

```sh
poetry -C backend run alembic upgrade head
```

The frontend from commit `b586555` works with these endpoints without changes.
Use HTTP mode (`VITE_DEMO_MODE=false`); demo mode still uses browser-only credits.
Credit accounts start at **zero**, including accounts created before this migration.
Credits never expire. The low-credit threshold is 25.

Credit endpoints follow the app's identity mode: account sessions when
`COURSE_MAKER_AUTH_ENABLED=true`, or the existing gateway key and signed owner cookie
in legacy mode. Both modes can read balances/history and purchase credits. Legacy
generation remains unmetered; automatic usage billing requires account mode. Signed
Stripe webhooks authenticate independently of the browser identity mode.

## Stripe setup

Set `COURSE_MAKER_STRIPE_SECRET_KEY` and `COURSE_MAKER_STRIPE_WEBHOOK_SECRET`.
Both may be empty to disable purchases (checkout and webhooks return 503).
Setting only one fails configuration validation. Secrets are never returned to browsers.
Use Stripe test-mode credentials for development; the implementation also supports live keys.

Register `POST /api/v1/credits/webhook` in Stripe with these events:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`

For local development, forward test events with the Stripe CLI:

```sh
stripe listen \
  --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired \
  --forward-to http://localhost:8000/api/v1/credits/webhook
```

Use the listener's `whsec_...` value as the local webhook secret. Restart the API after
changing its environment. The browser return origin comes from the existing validated
`COURSE_MAKER_AUTH_PUBLIC_URL`. Success returns to
`/credits?checkout=success&checkout_id=<local-checkout-id>`; cancellation returns to
`/credits?checkout=cancelled`. Cancelling in the browser does not grant credits or mark
a payment failed; an unused session eventually expires.

Docker Compose forwards the same Stripe and pricing variables to the API service;
provide them in the shell or the Compose environment file used to start the stack.

Create checkout **through the app**, then pay using Stripe's test payment methods.
A generic `stripe trigger` fixture lacks the app's saved checkout metadata and is
acknowledged without granting credits. No Stripe Products or Prices need manual setup:
the server sends the selected pack's fixed price as inline Checkout price data.
The REST adapter pins Stripe API version `2026-10-28.endive` and disables adaptive
pricing so webhook amount and currency match the saved USD purchase snapshot.

## API

Browser endpoints use the app's configured identity mode. Account-mode writes enforce
the existing origin/CSRF checks; legacy requests require the gateway key and signed
owner cookie. All responses use camelCase. The webhook uses the raw-body Stripe signature
instead of browser authentication, with a five-minute signature tolerance.

| Method | Path under `/api/v1/credits` | Result |
| --- | --- | --- |
| GET | base | `{credits}` |
| GET | `/packs` | `{packs: [{id, name, credits, bonusCredits, priceCents, currency, badge}]}` |
| GET | `/transactions?limit=20&cursor=...` | `{items: [{id, kind, credits, description, createdAt}], nextCursor}` |
| POST | `/checkout` with `{packId}` | `{checkoutId, url}` |
| GET | `/checkout/{checkoutId}` | `{status, creditsAdded}` |
| GET | `/policy` | `{costs, creditsExpire: false, lowCreditThreshold: 25}` |
| POST | `/webhook` | `{received: true}` |

Transaction history uses UTC ISO timestamps and stable keyset pagination, newest
first, with a maximum page size of 100. Cursors are opaque. Purchase transactions
include the pack's bonus credits in their positive total. Usage is negative, and
failed-operation refunds are positive. A checkout belonging to another account
returns 404. Polling checkout never changes balances.

Packs match the frontend demo: Starter is 100 credits for $5; Creator is 500 + 50
bonus for $20; Studio is 1500 + 250 bonus for $50. Prices and grants come exclusively
from the server catalog in `app/credits/domain/models.py`. Each checkout saves its
price and total credits, so changing the catalog cannot change an existing purchase.

## Usage pricing

`GET /policy` supplies action IDs and current costs for future cost previews.
Defaults are provisional product choices and configurable through environment values:

| Action IDs | Credits | Setting suffix after `COURSE_MAKER_` |
| --- | --- | --- |
| `lesson_create` | 1 | `CREDIT_CREATE_COST` |
| `lesson_generate`, `lesson_regenerate`, `course_generate`, `interactive_generate` | 5 | `CREDIT_GENERATE_COST` |
| `lesson_media` | 10 | `CREDIT_MEDIA_COST` |
| `lesson_automatic`, `course_automatic` | 25 | `CREDIT_AUTOMATIC_COST` |

Creating a standalone lesson costs 1. Planning, script generation, quiz regeneration,
style planning and thumbnail regeneration cost 5 per request. Storyboard, speech and
animation endpoints cost 10 each. Automatic/full video production costs 25 per request;
its internal stages, background thumbnails and automatically generated quizzes do not
add separate charges. Course syllabus/style/thumbnail generation costs 5. Creating,
changing or retrying an interactive build costs 5. Reads, publishing, manual edits,
copying existing content, cancellation and course metadata creation are free.

Reservations use a short independent database transaction before work begins.
Insufficient balances return HTTP 402 with a `detail` message before invoking the
lesson use case. Synchronous exceptions, including stale revisions and provider
failures, trigger an idempotent compensating refund. Accepted background interactive
jobs are charged when queued; later build failure/cancellation is currently charged.
Pricing is per request, including repeated successful requests; it is independent of
provider token costs. A process crash after reserving credits requires ledger review;
there is no durable reservation-recovery worker in this version.

## Consistency and verification

Stripe calls happen outside database transactions. A local checkout is persisted first
and also serves as the Stripe idempotency key. Fulfillment locks that checkout and the
credit account, validates the provider session, amount and currency, and commits the
balance, purchase ledger entry and paid status together. Replayed or concurrent events
cannot credit a checkout twice. Late failure/expiration events cannot undo a paid
purchase; delayed payments stay pending until their final event. Simultaneous spending
locks the account and cannot make the balance negative. Database constraints enforce
nonnegative balances and unique ledger references.

Stripe cash refunds and disputes do not currently change credit balances automatically;
their product policy and reconciliation are separate from usage-failure refunds.

The deterministic tests use disposable PostgreSQL, Redis and Mailpit containers, real
account sessions, and a mocked Stripe HTTP transport with real signature verification.
They do not make payments or require Stripe credentials:

```sh
poetry -C backend install --extras ai
poetry -C backend run pytest tests/unit/credits tests/integration/credits \
  tests/integration/users/authentication -q
```

The PostgreSQL suite covers concurrent fulfillment, concurrent spending/refunds,
rollback, migration constraints and ledger persistence. The authenticated smoke test
covers purchase → signed webhook → paid polling → lesson usage → failure refund and
account isolation. Test-mode payment through Stripe's hosted page remains the final
deployment check after real test credentials and webhook forwarding are configured.

## Existing-user grants

Use the audited grant command with the intended deployment's database configuration.
It previews the user IDs and balances by default:

```sh
poetry -C backend run python scripts/grant_existing_user_credits.py \
  --grant-id existing-users-2026-11-03 --credits 1000000
```

Add `--apply` to grant the credits. Each user receives an additional 1,000,000 credits
and a `bonus` ledger entry in the same transaction. The batch ID and user ID form a
unique reference, so retrying the same grant does not double-credit anyone. A batch
reads its recipient snapshot before applying grants; later signups are excluded from
that execution. Do not change the batch ID when retrying an interrupted execution.
