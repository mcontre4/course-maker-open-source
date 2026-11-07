# User accounts

Accounts are opt-in. With `COURSE_MAKER_AUTH_ENABLED=false` (the default), the application
keeps its previous API-key gateway, signed anonymous-owner cookies, local profile and shared
course-list behavior. No login is required, account endpoints return 404, and the email worker
does not start. Legacy mode can start against the pre-account `0013` schema; it still validates
all other required tables and columns. Existing account records and migrations are retained.

Set `COURSE_MAKER_AUTH_ENABLED=true` in the API environment to enable the account flow.
Run migration `0014` first, then restart the API and the Vite development/preview server.
The browser reads `/api/v1/auth/config` at runtime, so there is no separate frontend auth flag
or build required. Configuration errors do not silently fall back to legacy mode. Vite reads
the same backend environment and supplies the server-side service key only in legacy mode;
other reverse proxies must follow the same deployment mode. The key never enters the bundle.
Turning the flag off restores the previous access model, so keep its existing gateway restrictions.

When enabled, the browser signs in with an account session. The shared API key no longer authorizes
private course or lesson APIs. `/users` remains a service-key-protected legacy provisioning
endpoint; it does not create credentials or grant a login session. `/health/ready` also retains
service-key protection.

## What visitors can see without an account

With accounts enabled, the website itself is open to everyone. A visitor can use the home page,
Explore, search, public lessons and creator profiles without signing in. They sign in only to
make something or to open their own work.

- Open to visitors: `/`, `/explore`, `/watch/*`, `/creators/*` and the account pages.
- Needs an account: `/lessons/*` (including `/lessons/new`), `/courses/*`, `/library`, `/workspace`,
  `/settings`, `/credits` and `/internal/*`. The list lives in `frontend/src/course-maker/ui/auth-routes.ts`;
  add new private pages there.
- A visitor who opens a private page, chooses **Create**, or chooses **Copy lesson** on a public
  lesson goes to `/login?returnTo=…`. The page says what they were trying to do ("Sign in to create a
  lesson."), and signing in or creating an account brings them back to that page. Only same-site
  paths are accepted as `returnTo`.
- The home page does not request private data for visitors. It loads only the public discovery
  feed, so no request returns 401 and no private API is called. The API still enforces ownership:
  hiding a page in the browser is a convenience, not the access control.
- Someone who is already signed in and opens `/login` or `/signup` is sent straight on.

## Run locally

1. Install the locked backend dependencies with `poetry -C backend install --extras ai` and
   frontend dependencies with `npm --prefix frontend ci`.
2. Enable accounts with `COURSE_MAKER_AUTH_ENABLED=true`. Copy `backend/.env.example` to `backend/.env`, set a private service API key, and set
   `COURSE_MAKER_AUTH_PUBLIC_URL` to the **exact browser origin**, including the port.
3. Start the local stack:

   ```sh
   docker compose --env-file backend/.env up -d --build mailpit api
   ```

   The API dependency runs `alembic upgrade head`. For a standalone API process, run
   `poetry -C backend run alembic upgrade head` first and use `COURSE_MAKER_SMTP_HOST=localhost`
   to reach Mailpit's published SMTP port 1025. Compose uses hostname `mailpit`.
4. Run `npm --prefix frontend run dev`. Use `/signup` and open the local inbox at
   `http://localhost:8025` to verify the address. Sign in at `/login`.

The existing Compose database remains MySQL. Authentication mappings and migration `0014`
also support PostgreSQL (`postgresql+psycopg://…`); the account integration/browser tests use
disposable PostgreSQL instances. No existing database volume is replaced by this change.

## Google configuration

Create a Google OAuth **Web application** client for this application. Configure the consent
screen and allowed test users as required by Google, then set server-side environment variables:

```dotenv
COURSE_MAKER_GOOGLE_CLIENT_ID=<web-client-id>
COURSE_MAKER_GOOGLE_CLIENT_SECRET=<web-client-secret>
COURSE_MAKER_AUTH_PUBLIC_URL=https://your-app.example
```

Register this exact authorized redirect URI:

```text
https://your-app.example/api/v1/auth/google/callback
```

For local development the callback is, for example,
`http://localhost:5173/api/v1/auth/google/callback`. `localhost` and `127.0.0.1` are different
origins. Both client values must be present; otherwise Google is disabled and its button is
hidden. No Google secret belongs in `VITE_*`, browser storage, or the frontend bundle.

The backend uses authorization code + PKCE S256, a ten-minute single-use Redis state record,
an HttpOnly browser-binding cookie, and an ID-token nonce. It checks Google's RSA signature,
issuer, audience, authorized party, expiry, verified email and stable `sub` identity. It discards
provider access tokens and never uses an email address as Google's persistent identity.

An existing email/password account is **not automatically linked** to a Google identity with
the same email. Sign in using the original method. An explicit authenticated linking feature
would be a separate use case.

## Email delivery

Configure the following for a production SMTP relay:

```dotenv
COURSE_MAKER_SMTP_HOST=smtp.example.com
COURSE_MAKER_SMTP_PORT=587
COURSE_MAKER_SMTP_STARTTLS=true
COURSE_MAKER_SMTP_USERNAME=<relay-user>
COURSE_MAKER_SMTP_PASSWORD=<relay-secret>
COURSE_MAKER_MAIL_FROM=accounts@your-app.example
```

Each API process starts one outbox worker. Account changes, action-token digests and outbox
messages commit atomically. Workers claim messages with a database lease, commit, then perform
SMTP delivery outside the transaction. Failures retry with bounded backoff; crashes may cause
a duplicate email with the same message ID. The verification/reset action remains single-use.
Successful delivery deletes the message body; expired messages, actions and sessions are cleaned
up. Pending message bodies contain live links, so restrict database/backups and outbox access.
Monitor `Account email delivery failed` / `Account outbox unavailable` warnings and queue age.

## Security and deployment behavior

- Passwords use Argon2id (64 MiB, three iterations, one lane), unique salts, a 15–128 character
  policy, and an offline common-password denylist. Unicode, spaces, paste and password managers
  are supported. Passwords are not stripped or truncated. The bundled denylist is a baseline,
  not an exhaustive breach corpus; its source, digest and license are included beside it.
- Email accounts must verify ownership before signing in. Verification links expire after 24
  hours; password reset links expire after 30 minutes. Resending replaces the previous link.
  Resetting a password revokes all existing sessions and requires a fresh login.
- Random 256-bit session secrets live only in HttpOnly, SameSite=Lax cookies. Only SHA-256
  digests are stored in the session table. HTTPS enables Secure, host-only `__Host-` cookies.
  HTTP is permitted only for loopback development origins. Sessions expire after eight hours
  absolutely or 30 minutes idle by default. Activity refreshes idle time without extending the
  absolute deadline. Durations are configurable with `AUTH_SESSION_SECONDS` / `AUTH_IDLE_SECONDS`
  under the usual `COURSE_MAKER_` prefix.
- State-changing account and private API requests require both the exact configured Origin and
  a CSRF token obtained from `/api/v1/auth/session`. The CSRF secret is also in an HttpOnly cookie;
  the browser client retains the response token in memory. SameSite is an additional defense.
- Redis atomically limits account requests by network peer and normalized-email fingerprint.
  Missing Redis fails closed with 503. Limits return 429 and Retry-After. Do not expose Redis
  publicly. Configure Uvicorn's trusted proxy addresses explicitly; do not trust arbitrary
  forwarded headers or expose the API port around the reverse proxy.
- Private ownership derives from the authenticated user ID. Clients cannot select it using
  headers, request bodies, the old anonymous owner cookie, or the shared API key. Course lists
  are scoped by owner. Private cross-account access returns 404. Published content remains public.
- Authentication responses are non-cacheable, validation responses omit original secret input,
  and account audit messages omit passwords, codes, tokens and email addresses. The callback
  query is scrubbed before Uvicorn access logging. Configure upstream/CDN access logs to omit
  callback query strings too. Verification/reset secrets use URL fragments and are removed
  from the current history entry when submitted.
- Serve the frontend and `/api` under the same HTTPS origin; forward cookies and Origin unchanged.
  The Vite development/preview proxy supplies no service key. Production hosting must supply the
  same-origin reverse proxy and SPA route fallback. Set appropriate frontend security headers at
  that hosting layer; preserve the application's intentionally sandboxed interactive previews.
- Account changes cancel in-flight application requests and unread response bodies, clear the
  client query cache, and remount account-specific screens. Late replies from an earlier account
  are rejected before they can repopulate that cache. An expired
  session returns the user to login. Authenticated identity is not taken from the old browser
  profile store; the sign-in email is read-only in profile settings.

The account/application/domain/ports/adapters live within the existing users bounded context.
Every use case exposes `execute(Request) -> Response`; DTOs are immutable. Time, IDs, token
generation, password hashing, Google I/O, persistence and Redis flow storage are injected ports.
Composition roots connect authenticated identity to courses without cross-domain imports.

## Existing data and rollout

Run migration `0014` before starting the updated API. It normalizes existing user emails and
adds accounts, sessions, one-time actions and the mail outbox. Reconcile any case-insensitive
email collisions before migration; migration fails rather than selecting an identity for you.
Test a backup restoration and migration on a disposable copy before a production rollout.

Existing anonymous owner cookies and legacy user records do not automatically claim an account
or transfer private content. Published material stays public. An explicit, verified migration
of old anonymous content can be added separately. This prevents a newly registered email or
an unsigned client identifier from claiming someone else's content.

Live Google consent and production SMTP delivery require the deployment's real configuration.
The tests replace Google's external provider port; no live Google account or paid provider is used.
This implementation follows the cited guidance; it is not a compliance certification.

## Verification

```sh
poetry -C backend run pytest tests/unit
poetry -C backend run pytest tests/integration/users/authentication tests/integration/creators
poetry -C backend run mypy
poetry -C backend run ruff check src tests
poetry -C backend run tach check
python backend/scripts/check_hexagonal_boundaries.py --root backend/src
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e:auth
npm --prefix frontend run test:e2e:legacy-auth
npm --prefix frontend run test:e2e
```

Docker is required for infrastructure/browser suites. The dedicated account browser suite uses
the production app and migrations, real PostgreSQL/Redis/SMTP, and an injected Google provider.
Separate adapter tests verify actual RSA-signed ID tokens and reject forged signatures and
invalid issuer/audience/expiry/nonce/verification claims. The older content browser suite keeps
its explicit pinned test identity so it can focus on course/media behavior.
The frontend CI workflow runs the account browser suite in a separate job without provider secrets.

References: [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).
