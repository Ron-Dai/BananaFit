# Validation Record

Validation was executed locally on September 12, 2026, from the repository state based on commit `ddee2fe2aece843228bffe0509ff95746bbcc184`.

## Environment

- Python: CPython 3.12
- Component version: `sexybanana-accounts 0.1.0`
- Validation dependencies: the exact direct versions in `requirements-dev.lock`
- Runtime provider default: the existing `DeepSeekProvider` through OpenRouter
- AI provider used for automated plan-generation tests: an injected local stub or `FakeProvider`; the automated suite makes no external AI request

## Executed checks

### Account component tests

```text
38 passed
```

The tests cover registration, password validation and hashing, duplicate accounts, login failure behavior, session cookies, expiration, logout, CSRF, trusted origins, database migrations and permissions, concurrent registration, user-to-session ownership, plan ownership, current-plan responses, cross-user URL manipulation, public field filtering, account deletion, English pages, security headers, default DeepSeek injection, environment overrides, explicit offline provider selection, explicit provider consent, ownership-protected consent updates, and safe translation of fitness-intake validation errors.

The test runner emitted two dependency deprecation warnings from FastAPI/Starlette test utilities. They do not represent component failures.

### Existing fitness-intake regression tests

```text
120 passed
```

The existing `fitness_intake` component was not modified.

### Static checks

```text
ruff check user_accounts
All checks passed!
```

Python bytecode compilation also completed without errors for the component source and examples.

### Package build and resource check

The project built `sexybanana_accounts-0.1.0-py3-none-any.whl`. A clean target-directory installation successfully imported the package, created the FastAPI application, and located all four packaged browser resources:

- `templates/login.html`
- `templates/register.html`
- `static/auth.css`
- `static/auth.js`

### Shared-database integration check

A temporary SQLite database was opened by both `fitness_intake.SQLiteStore` and `AccountDatabase`. The check created an account, created a fitness-intake session through the account service, established ownership, and retrieved that session as its owner. The `sessions`, `users`, `auth_sessions`, `fitness_session_owners`, and `workout_plans` tables coexisted in the same database.

### Authorized live provider check

After the repository owner explicitly authorized a live call using the current free API, an end-to-end check used fictional fitness data and a temporary database. The default builder injected `DeepSeekProvider` through OpenRouter, the provider returned a plan with `ready` status, fitness-intake validated all fourteen days, the account service saved the user-to-session and user-to-plan associations, and `get_current_plan_for_user` returned the same fourteen-day plan as `available`. No real user data was transmitted.

### Browser rendering check

The standalone server returned the login page, registration page, CSS, JavaScript, and CSRF endpoint successfully in a local browser. Both pages rendered in English with the established ForgeFit visual palette and typography.

### Repository scope check

All new tracked candidates are below `user_accounts/`. There are no tracked-file differences from `origin/main` outside this new component. SHA-256 comparisons confirmed these existing files are unchanged:

- `frontend/src/main.jsx`
- `server.py`
- `main.py`

The existing `Ron Forge` text remains in `frontend/src/main.jsx`. No database file is present in the new component's tracked candidates. The account component obtains the project owner's explicitly authorized temporary development credential from the existing `fitness_intake` configuration and does not carry a duplicate key.

## Result

The component passed its automated, integration, packaging, browser, and repository-scope checks. It is ready for local review and manual Git commit or push using the steps in `README.md`.
