# SexyBanana User Accounts and Workout Plan Ownership

`sexybanana-accounts` is an isolated authentication, authorization, and workout-plan access component for SexyBanana. It provides English registration and login pages, Argon2id password hashing, revocable server-side sessions, SQLite persistence, CSRF and CORS controls, user-to-intake ownership, user-to-plan ownership, and a dashboard-oriented current-plan API.

The component is designed around the repository that existed at commit `ddee2fe2aece843228bffe0509ff95746bbcc184`. It does not replace the React/Vite frontend, FastAPI video service, computer-vision pipeline, exercise modules, or fitness-intake engine. The existing `Ron Forge` frontend text remains unchanged and is treated as established application branding.

Importing this package starts no server, creates no account, and makes no network request. The standalone application now injects the existing fitness-intake engine with its DeepSeek/OpenRouter provider by default. External calls occur only when an intake method actually requests model work, and the existing fitness-intake consent checks still apply.

## What the component owns

The component owns four boundaries:

1. Account registration and password verification.
2. Opaque, revocable browser sessions.
3. Server-established ownership of fitness-intake sessions and plans.
4. A small public plan representation suitable for the existing dashboard.

It does not own pose detection, camera capture, exercise classification, equipment detection, medical interpretation, or the generation rules inside `fitness_intake`.

The component serves `/login` and `/register` itself. A successful registration signs the new account in, and a successful login redirects to the configured existing application URL. Direct access to the existing application page may still be possible until its host adds an authentication guard, but protected account, intake, and plan APIs always require a valid account session.

## Architecture

```text
Browser
  ├── GET /login or /register
  ├── CSRF token + credential POST
  └── HttpOnly session cookie
              │
              ▼
       Account FastAPI router
          ├── AccountService
          ├── Argon2id Passwords
          ├── AccountDatabase
          └── FitnessIntakeService adapter
                    │
                    ▼
              SQLite database
          ├── users
          ├── auth_sessions
          ├── fitness_session_owners
          ├── workout_plans
          └── sessions (owned by fitness_intake)
```

The authentication account ID and the fitness-intake `participant_id` are deliberately separate. A server-created row in `fitness_session_owners` connects them. The browser never chooses the owner ID.

## Directory map

```text
user_accounts/
├── README.md                         This integration guide
├── VALIDATION.md                     Executed checks and their results
├── pyproject.toml                    Installable Python package
├── requirements-dev.lock             Tested dependency versions
├── .env.example                      Local configuration example
├── examples/
│   ├── standalone_server.py          Independent local server
│   ├── fastapi_integration.py        Future host-router integration
│   └── plan_api_client.py            Cookie and CSRF API walkthrough
├── src/sexybanana_accounts/
│   ├── app.py                        Standalone app factory and handlers
│   ├── router.py                     HTML and HTTP API routes
│   ├── service.py                    Authentication and ownership rules
│   ├── database.py                   SQLite schema and queries
│   ├── configuration.py              Environment-backed settings
│   ├── fitness.py                    DeepSeek/Fake provider injection factory
│   ├── passwords.py                  Argon2id boundary
│   ├── csrf.py                       CSRF and Origin checks
│   ├── models.py                     Strict request/response models
│   ├── errors.py                     Stable safe errors
│   ├── templates/                    English login and registration pages
│   └── static/                       Matching CSS and browser form logic
└── tests/                             Offline security and contract tests
```

## Requirements

- CPython 3.11 or later.
- The local `fitness_intake` package when intake ownership or plan generation is required.
- SQLite, included with standard CPython.

## Installation

From the SexyBanana repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./fitness_intake
python -m pip install -e './user_accounts[dev]'
```

PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ./fitness_intake
python -m pip install -e './user_accounts[dev]'
```

The package name is `sexybanana-accounts`; the import name is `sexybanana_accounts`.

## Configuration

Copy values from `.env.example` into the host environment. The package uses the `SEXYBANANA_` prefix.

| Variable | Development default | Meaning |
| --- | --- | --- |
| `SEXYBANANA_DATABASE_PATH` | `data/sexybanana.db` | Shared local SQLite path |
| `SEXYBANANA_APP_URL` | `http://localhost:5173/` | Fixed redirect after registration or login |
| `SEXYBANANA_ALLOWED_ORIGINS` | Local frontend and auth origins | Comma-separated credentialed CORS and CSRF origins |
| `SEXYBANANA_COOKIE_NAME` | `sexybanana_session` | Opaque session cookie name |
| `SEXYBANANA_COOKIE_SECURE` | `false` | Set `true` behind production HTTPS |
| `SEXYBANANA_SESSION_LIFETIME_SECONDS` | `43200` | Session lifetime, from 300 to 2,592,000 seconds |
| `SEXYBANANA_AUTH_HOST` | `127.0.0.1` | Standalone bind host |
| `SEXYBANANA_AUTH_PORT` | `8001` | Standalone port |
| `SEXYBANANA_FITNESS_PROVIDER` | `deepseek` | `deepseek` for the live provider or `fake` for explicit offline development |

The live fitness provider uses the existing fitness-intake configuration names:

| Variable | Development default | Meaning |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Bundled by `fitness_intake` for development | Overrides the fitness module's authorized source fallback |
| `DEEPSEEK_MODEL` | `deepseek/deepseek-chat` | OpenRouter model identifier |
| `DEEPSEEK_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible HTTPS endpoint |
| `DEEPSEEK_TIMEOUT_SECONDS` | `45` | Request timeout |
| `DEEPSEEK_MAX_RETRIES` | `2` | Bounded retry count |
| `DEEPSEEK_MAX_TOKENS` | `6000` | Maximum response tokens |
| `DEEPSEEK_TEMPERATURE` | `0` | Deterministic sampling preference |

The `fitness_intake` dependency contains the project owner's explicitly authorized OpenRouter key as a temporary source fallback in its `providers.py`. This account adapter calls `DeepSeekConfig.from_env()` instead of carrying a second copy. Environment variables take priority. Remove the fallback from `fitness_intake` and rotate the key before a public or production release. The value is wrapped in `SecretStr` at runtime and is never returned by an API or written to the database, but source-level inclusion means anyone who can read the repository can copy it.

`SEXYBANANA_APP_URL` must be an absolute HTTP or HTTPS URL and cannot contain embedded credentials or a fragment. It is read from trusted server configuration. The component does not accept a client-provided redirect destination, preventing open redirects.

`SEXYBANANA_ALLOWED_ORIGINS` must enumerate every trusted origin. Never use a wildcard with credentialed cookies. Include the exact production scheme and host. A trailing slash is normalized away.

The package does not load a repository `.env` automatically. The process manager, deployment service, or developer shell supplies environment variables.

## Standalone local run

The standalone app does not modify the repository's existing `server.py`:

```bash
source .venv/bin/activate
cd user_accounts
python examples/standalone_server.py
```

Alternatively:

```bash
python -m sexybanana_accounts
```

Open:

```text
http://127.0.0.1:8001/register
```

The standalone factory uses `build_fitness_service(settings)`. With the default `SEXYBANANA_FITNESS_PROVIDER=deepseek`, it constructs the existing `FitnessIntakeService` with `DeepSeekProvider` and a shared `SQLiteStore`. Login, registration, session creation, and ordinary database reads do not contact the provider. A model request occurs only when the fitness-intake flow performs free-text extraction or generates a ready plan. Set `SEXYBANANA_FITNESS_PROVIDER=fake` for explicit offline development.

The external provider does not bypass the fitness-intake consent model. Before model-assisted extraction or planning, the session must include the consent required by `fitness_intake`; otherwise that module returns `consent_required` instead of sending data.

Registration automatically creates a server-side session and redirects to `SEXYBANANA_APP_URL`. Registration proves that the submitted address is syntactically valid and unique in this database. It does not verify ownership of the email address; no email delivery is included.

## Authentication flow

1. The page obtains a fresh token from `GET /api/auth/csrf`.
2. The browser stores the matching readable CSRF cookie.
3. The form sends the token in `X-CSRF-Token` and submits JSON.
4. The server validates the CSRF cookie, header, and any supplied `Origin`.
5. Registration hashes the password with Argon2id. Login always performs an Argon2 verification, including a dummy verification for unknown accounts, reducing timing-based account enumeration.
6. The server generates a cryptographically random opaque session token.
7. Only the SHA-256 digest of that token is stored in `auth_sessions`.
8. The raw token is returned only in an `HttpOnly`, `SameSite=Lax` cookie.
9. The browser redirects to the fixed configured application URL.

Passwords require 12–256 characters, at least one letter, at least one digit, and no leading or trailing whitespace. The plaintext value is never saved or logged.

## Cookies and browser security

The authentication cookie has:

- `HttpOnly`, so frontend JavaScript cannot read it.
- `SameSite=Lax`, reducing cross-site request attachment.
- `Path=/`.
- An explicit maximum age.
- A configurable `Secure` flag that must be enabled under production HTTPS.

The CSRF cookie is intentionally readable because it participates in the double-submit pattern. Matching the cookie alone is insufficient: state-changing requests must send the same value in `X-CSRF-Token`, and a supplied browser `Origin` must be trusted.

Authentication pages and authentication responses use `Cache-Control: no-store`. The standalone app also sets `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: same-origin`.

Do not store session tokens in local storage, session storage, URL parameters, logs, or application JSON.

## Database

The default database is `data/sexybanana.db`. The component creates its parent directory with owner-only permissions and the database file with mode `0600`. Runtime data is excluded by `user_accounts/.gitignore`.

Each connection enables:

```sql
PRAGMA foreign_keys=ON;
PRAGMA secure_delete=ON;
PRAGMA busy_timeout=10000;
```

Migrations are versioned in `account_schema_migrations` and are idempotent. Migration version 1 creates:

### `users`

```text
id                  server-generated public identifier
email_normalized    normalized unique email
password_hash       Argon2id encoding, never plaintext
created_at          timezone-aware timestamp
updated_at          timezone-aware timestamp
is_active           account availability flag
```

### `auth_sessions`

```text
id          server-generated session record ID
user_id     foreign key to users
token_hash  unique SHA-256 digest
created_at  creation timestamp
expires_at  expiration timestamp
revoked_at  null until logout or revocation
```

### `fitness_session_owners`

```text
fitness_session_id  existing fitness-intake session ID
user_id             foreign key to users
created_at          ownership creation timestamp
```

`fitness_session_id` is the primary key, so one fitness-intake session cannot be attached to multiple accounts.

### `workout_plans`

```text
id                      account component's public plan record ID
user_id                 owning account
fitness_session_id      owning intake session
fitness_plan_id         validated fitness-intake plan ID
source_profile_version  fitness profile version used for generation
status                  available or stale
plan_json               validated source plan snapshot
created_at              creation timestamp
updated_at              update timestamp
```

A composite foreign key requires the plan's `(fitness_session_id, user_id)` pair to exist in `fitness_session_owners`.

SQLite is suitable for local development and a single application process. Production deployments with multiple application replicas should migrate the repository and query implementations to PostgreSQL while preserving the `AccountService` contract. Production also needs managed backups, encryption at rest, operational key management, monitoring, and a tested restoration procedure.

## Public HTTP API

### Obtain CSRF token

```http
GET /api/auth/csrf
```

```json
{"csrf_token":"opaque-value"}
```

### Register

```http
POST /api/auth/register
Content-Type: application/json
X-CSRF-Token: opaque-value
```

```json
{
  "email": "person@example.com",
  "password": "long-password-123",
  "password_confirmation": "long-password-123"
}
```

A successful response is `201`, sets the session cookie, and returns the fixed redirect:

```json
{
  "authenticated": true,
  "user": {
    "id": "user_...",
    "email": "person@example.com",
    "created_at": "2026-09-13T12:00:00+00:00"
  },
  "expires_at": "2026-09-14T00:00:00+00:00",
  "redirect_url": "http://localhost:5173/"
}
```

### Login

```http
POST /api/auth/login
```

```json
{"email":"person@example.com","password":"long-password-123"}
```

The response has the same authenticated envelope as registration.

### Current account

```http
GET /api/auth/me
Cookie: sexybanana_session=...
```

```json
{
  "authenticated": true,
  "user": {
    "id": "user_...",
    "email": "person@example.com",
    "created_at": "2026-09-13T12:00:00+00:00"
  }
}
```

Password hashes, session hashes, internal row numbers, and fitness data are never included.

### Logout

```http
POST /api/auth/logout
X-CSRF-Token: opaque-value
```

Logout is idempotent. It revokes a known server session and clears the cookie.

### Create an owned intake session

```http
POST /api/intake/sessions
Cookie: sexybanana_session=...
X-CSRF-Token: opaque-value
```

The server derives the owner from the cookie. Query or body values named `user_id` do not influence ownership.

The request body may record explicit external-processing consent for the new session:

```json
{
  "consent": {
    "external_ai": true,
    "sensitive_sections": [],
    "attachments": false,
    "purpose": "Fitness intake and fourteen-day planning"
  }
}
```

Omitting the body creates the session with external AI disabled. Consent must reflect an actual user choice; a host must not silently set it to `true`. Authorize only the sensitive sections or attachment processing the user actually accepted.

```json
{"session_id":"session_...","version":0}
```

### Update consent for an owned intake session

```http
POST /api/intake/sessions/{fitness_session_id}/consent
X-CSRF-Token: opaque-value
```

```json
{
  "consent": {
    "external_ai": true,
    "sensitive_sections": [],
    "attachments": false,
    "purpose": "Fitness intake and fourteen-day planning"
  },
  "expected_version": 0
}
```

The endpoint verifies ownership before updating consent and uses `expected_version` for optimistic concurrency. Another user's session ID and an unknown ID return the same `404` response.

### Read an owned intake session

```http
GET /api/intake/sessions/{fitness_session_id}
```

The lookup checks `(authenticated_user_id, fitness_session_id)` before loading the fitness data. A missing ID and another user's ID both return the same `404` error.

### Generate and save a plan

```http
POST /api/intake/sessions/{fitness_session_id}/generate-plan
X-CSRF-Token: opaque-value
```

```json
{
  "start_date": "2026-09-14",
  "timezone": "America/New_York",
  "expected_version": 8
}
```

Generation occurs only after ownership verification. A successful validated fitness plan is saved with the same authenticated account ID and intake session ID. If readiness is incomplete, the endpoint returns readiness and a `current_plan` state without inventing a plan.

### List owned plans

```http
GET /api/plans
```

```json
{"plans":[]}
```

Only rows with the authenticated account's server-derived ID are returned.

### Get one owned plan

```http
GET /api/plans/{account_plan_id}
```

The path uses the account plan record ID, such as `userplan_...`. Supplying another user's valid plan ID produces the same response as an unknown ID.

## Current plan API for the dashboard

`GET /api/plans/current` is the main future frontend integration point. It returns the newest plan owned by the signed-in account without exposing the fitness-intake session's unrelated health answers.

No plan:

```json
{"status":"none","plan":null}
```

Available plan:

```json
{
  "status": "available",
  "plan": {
    "id": "userplan_...",
    "fitness_plan_id": "plan_...",
    "fitness_session_id": "session_...",
    "source_profile_version": 4,
    "stale": false,
    "start_date": "2026-09-14",
    "end_date": "2026-09-27",
    "objective": "Health, Strength",
    "summary": {
      "duration_days": 14,
      "training_days": 6,
      "rest_days": 8,
      "completed_days": 2,
      "next_training_day": 4,
      "next_session_title": "Wall push-up",
      "next_session_minutes": 25.0,
      "target_muscle_groups": ["Chest", "Shoulders", "Triceps"]
    },
    "days": [],
    "generated_at": "2026-09-13T12:00:00+00:00"
  }
}
```

Stale plan:

```json
{
  "status": "stale",
  "plan": {
    "stale": true
  }
}
```

The actual stale response contains the full public plan. `stale=true` means the fitness-intake profile changed after plan generation or the source plan was explicitly marked stale. A dashboard must display a reassessment state rather than presenting it as a current prescription.

### Dashboard field mapping

| Existing dashboard need | Response field |
| --- | --- |
| Today's or next workout heading | `plan.summary.next_session_title` |
| Estimated duration | `plan.summary.next_session_minutes` |
| Target muscle labels | `plan.summary.target_muscle_groups` |
| Fourteen-day date range | `plan.start_date`, `plan.end_date` |
| Plan goal | `plan.objective` |
| Training/rest totals | `plan.summary.training_days`, `rest_days` |
| Completion progress | `plan.summary.completed_days / duration_days` |
| Day cards | `plan.days` |
| Exercise name and dose | `plan.days[].blocks[]` |
| Reassessment banner | `status === "stale"` or `plan.stale` |

Each public day contains:

```text
day, date, kind, objective, total_minutes, completed, blocks
```

Each public block contains only:

```text
exercise_id, name, phase, active_minutes, rest_minutes,
sets, repetitions, rpe, equipment, instructions
```

Internal constraints, answer IDs, raw health responses, authentication metadata, provider prompts, and password data are omitted.

### Future React consumption

This task deliberately does not modify `frontend/`. A future developer can add an API helper resembling:

```javascript
export async function loadCurrentPlan() {
  const response = await fetch(
    "http://localhost:8001/api/plans/current",
    { credentials: "include" }
  );

  if (response.status === 401) {
    window.location.assign("http://localhost:8001/login");
    return null;
  }

  if (!response.ok) {
    throw new Error("The workout plan could not be loaded.");
  }

  return response.json();
}
```

Recommended frontend states:

- Loading: retain a neutral skeleton or progress indicator.
- `none`: invite the user to complete intake; do not show hard-coded plan data as personal data.
- `available`: populate the dashboard from `result.plan`.
- `stale`: show the plan as requiring reassessment and avoid presenting it as current.
- `401`: redirect to the authentication component's `/login` page.
- Network or `5xx`: show a retryable service error without clearing local UI state.

Render returned text as text, never as raw HTML.

## Python integration API

Create the service explicitly:

```python
from sexybanana_accounts import AccountDatabase, AccountService, AccountSettings
from sexybanana_intake import DeepSeekConfig, DeepSeekProvider, FitnessIntakeService, SQLiteStore

settings = AccountSettings.from_env()
database = AccountDatabase(settings.database_path)
fitness_service = FitnessIntakeService(
    provider=DeepSeekProvider(DeepSeekConfig.from_env()),
    store=SQLiteStore(settings.database_path),
)
accounts = AccountService(settings, database, fitness_service)
```

The account component also provides the exact default injection used by the standalone application:

```python
from sexybanana_accounts import AccountSettings, build_fitness_service

settings = AccountSettings.from_env()
fitness_service = build_fitness_service(settings)
```

`build_fitness_service` shares `settings.database_path` with `SQLiteStore` and selects the configured live or fake provider. Passing a `fitness_service` explicitly to `create_app` still takes priority, which keeps tests and alternative providers isolated.

`BaseSettings` reads environment variables during construction; `AccountSettings()` is equivalent when no explicit overrides are passed.

Important methods:

| Method | Purpose |
| --- | --- |
| `register(email, password)` | Create a normalized account with an Argon2id password hash |
| `login(email, password)` | Verify credentials and create an opaque server session |
| `authenticate(raw_token)` | Resolve a current nonexpired principal |
| `logout(raw_token)` | Revoke a session idempotently |
| `create_fitness_session_for_user(user_id, **kwargs)` | Create a fitness session and atomically attempt ownership attachment |
| `claim_fitness_session_for_user(user_id, session_id)` | Host-only migration helper for an existing unowned session |
| `assert_fitness_session_owner(user_id, session_id)` | Apply uniform non-disclosing ownership enforcement |
| `get_fitness_session_for_user(user_id, session_id)` | Load an intake session only after ownership checks |
| `update_fitness_consent_for_user(user_id, session_id, consent, ...)` | Update provider consent only after ownership checks |
| `generate_plan_for_user(user_id, session_id, **kwargs)` | Verify ownership, generate, validate, and save the plan |
| `save_plan_for_user(user_id, session_id, plan)` | Save a previously validated plan idempotently |
| `get_plan_for_user(user_id, account_plan_id)` | Return one sanitized owned plan |
| `get_current_plan_for_user(user_id)` | Return `available`, `none`, or `stale` for the dashboard |
| `list_plans_for_user(user_id)` | List sanitized plans for one account |
| `delete_user_data(user_id)` | Delete component-owned fitness sessions, then cascade the account records |

`claim_fitness_session_for_user` is intentionally not exposed as a browser endpoint. It is for a trusted host migration where the caller has already established ownership outside this component. Never allow a browser to claim an arbitrary session identifier.

## Mounting the router in an existing FastAPI host

The component can be integrated without changing its internal code:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sexybanana_accounts import (
    AccountDatabase,
    AccountService,
    AccountSettings,
    build_fitness_service,
    create_router,
    install_exception_handlers,
)
settings = AccountSettings()
fitness_service = build_fitness_service(settings)
account_service = AccountService(
    settings,
    AccountDatabase(settings.database_path),
    fitness_service,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
install_exception_handlers(app)
app.include_router(create_router(account_service))
```

See `examples/fastapi_integration.py`. The repository's current `server.py` remains untouched. A future integrator should merge this router setup with its existing video route and keep a single `FastAPI` instance.

If the frontend and API use different origins in production, cookie behavior depends on the deployment domain and browser rules. Prefer a same-site reverse-proxy layout. Test the exact production cookie, CORS, CSRF, and TLS configuration rather than disabling those controls.

## Ownership and IDOR prevention

The browser never supplies an authoritative user ID. Each protected route:

1. Reads the opaque cookie.
2. Hashes the token.
3. loads a nonexpired, nonrevoked server session.
4. Derives the account ID from that database row.
5. Includes the account ID in the resource query.

The plan query is equivalent to:

```sql
SELECT *
FROM workout_plans
WHERE id = ? AND user_id = ?;
```

The fitness-session ownership query is equivalent to:

```sql
SELECT 1
FROM fitness_session_owners
WHERE fitness_session_id = ? AND user_id = ?;
```

An existing object owned by somebody else and a nonexistent object both produce:

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found."
  }
}
```

Changing a URL, plan ID, session ID, query string, hidden field, or JSON `user_id` cannot change the derived owner.

Python callers remain trusted backend code. A host must never pass a browser-supplied user ID directly into `AccountService`; first authenticate the server session and use `principal.user.id`.

## Error contract

Errors use:

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "The email or password is incorrect."
  }
}
```

| Code | Typical HTTP status | Meaning |
| --- | ---: | --- |
| `invalid_request` | 400/422 | Shape, type, or plan contract is invalid |
| `invalid_email` | 422 | Email syntax is invalid |
| `weak_password` | 422 | Password policy failed |
| `password_mismatch` | 422 | Confirmation differs |
| `account_exists` | 409 | Normalized email is already registered |
| `invalid_credentials` | 401 | Email or password is incorrect |
| `account_disabled` | 403 | Account is inactive |
| `authentication_required` | 401 | Session is absent, invalid, or revoked |
| `session_expired` | 401 | Known session has expired |
| `csrf_failed` | 403 | Token or trusted Origin check failed |
| `not_found` | 404 | Resource is missing or is not owned by this account |
| `version_conflict` | 409 | Fitness session changed during a versioned operation |
| `plan_unavailable` | 503 | Fitness integration is not configured |
| `plan_stale` | 409 | Reserved for callers that require a current plan |
| `database_failure` | 500 | Safe persistence failure |

Responses do not expose SQL, database paths, tokens, hashes, stack traces, or whether another account owns an identifier.

## Data deletion

`AccountService.delete_user_data(user_id)` performs component-level deletion:

1. Lists fitness-intake sessions owned by the account.
2. Calls the configured fitness service's idempotent `delete_session` for each.
3. Deletes the user row.
4. SQLite foreign-key cascades remove authentication sessions, ownership rows, and account plan snapshots.

There is no public browser account-deletion endpoint in this release. A host must add a separate reauthentication and confirmation flow before exposing deletion.

Database deletion cannot remove host backups, exported JSON, logs outside this component, provider-held data, or external attachments. The host owns those retention boundaries.

## Testing

All default tests are offline and use fictional accounts, temporary SQLite files, and a local fitness stub.

```bash
source .venv/bin/activate
pytest -q user_accounts/tests
ruff check user_accounts
pytest -q fitness_intake/tests
```

Coverage includes registration, normalization, password policy, Argon2 hashes, duplicate accounts, login, generic credential failures, cookies, session expiration, logout, CSRF, trusted origins, migration idempotency, file permissions, foreign keys, concurrent duplicate inserts, fitness ownership, plan ownership, repeated saves, missing/stale/current plan contracts, cross-user plan IDs, cross-user fitness session IDs, ignored client identity, public field filtering, pages, and security headers.

The component tests do not call DeepSeek, OpenRouter, a camera, an email provider, or GitHub.

## Troubleshooting

### `ModuleNotFoundError: sexybanana_accounts`

Install the component in the active Python environment:

```bash
python -m pip install -e './user_accounts[dev]'
```

### Fitness routes return `plan_unavailable`

Install `fitness_intake`. The default application factory injects it automatically. If the host deliberately disables that package boundary, pass a `FitnessIntakeService` to `AccountService` or `create_app`.

### Browser receives `csrf_failed`

Fetch `/api/auth/csrf` with credentials, retain the cookie, send the returned value in `X-CSRF-Token`, and add the exact browser origin to `SEXYBANANA_ALLOWED_ORIGINS`.

### Cookie is not sent

Confirm the frontend request uses `credentials: "include"`, the origins are configured, and production uses compatible HTTPS, domain, and `Secure` settings. Do not solve this by exposing the token to JavaScript.

### Registration redirects to the wrong application

Set `SEXYBANANA_APP_URL` on the authentication server. The client cannot override it.

### `database is locked`

SQLite has a ten-second busy timeout and short transactions. Ensure all application processes use a compatible SQLite access pattern. Move multi-replica production deployments to PostgreSQL.

### Current plan returns `none`

Registration alone does not generate a plan. The authenticated account must own a sufficiently complete fitness-intake session, and generation must return a validated plan.

### Current plan returns `stale`

The fitness profile changed after generation. Reassess and generate a new plan rather than clearing the flag in frontend code.

## Extension points and limitations

- Add email verification through a host-owned delivery service; current registration does not verify mailbox ownership.
- Add password reset only with expiring, single-use, hashed reset tokens and generic account responses.
- Add a production rate limiter at the reverse proxy or shared data layer. This local component does not provide a distributed brute-force limiter.
- Migrate SQLite query implementations to PostgreSQL for multiple replicas.
- Add a deliberate frontend authentication guard later; this task does not edit the existing React application.
- Add account deletion only with reauthentication and an explicit user confirmation flow.
- Add structured workout execution endpoints when the dashboard begins writing completion data.
- Keep AI provider credentials on the Python server. Never place them in the React bundle or plan response.
- Treat returned instructions as text. The public plan serializer does not return arbitrary HTML.

## End-to-end integration sequence

1. Install `fitness_intake` and `user_accounts` in the same Python environment.
2. Configure one SQLite path for the local account database and `SQLiteStore`.
3. Construct the fitness service with the desired provider.
4. Construct `AccountDatabase` and `AccountService`.
5. Mount `create_router(account_service)` and install the safe exception handlers.
6. Configure exact credentialed CORS origins.
7. Run migrations by constructing `AccountDatabase`.
8. Open `/register` and create a fictional development account.
9. Confirm the response sets an `HttpOnly` session and redirects to the existing application URL.
10. Create an intake session through the authenticated endpoint or Python service method, recording external AI consent only after an actual user choice.
11. Collect and confirm intake answers through the existing fitness-intake public API.
12. Call `generate_plan_for_user`, which verifies ownership before generation and saves the validated result.
13. Request `/api/plans/current` using the browser session cookie.
14. Populate the future dashboard using the documented summary and day fields.
15. Show a reassessment state whenever the response is stale.
16. Confirm a second fictional account receives `404` for the first account's session and plan identifiers.

This design keeps authentication and ownership at the host boundary while preserving the fitness-intake component as a reusable planning domain service.

## Manual Git handoff

The component was prepared on the local `feature/auth-user-plans` branch. Review the candidate files before committing:

```bash
git status --short
git diff -- user_accounts
```

Because the component is currently new and untracked, add only its directory, inspect the staged change, and create the local commit:

```bash
git add user_accounts
git diff --cached --stat
git diff --cached
git commit -m "Add authentication and user plan ownership component"
```

The repository owner can then publish the branch manually:

```bash
git push -u origin feature/auth-user-plans
```

These commands intentionally add only `user_accounts/`. Do not use `git add .` when unrelated local files are present.
