# BananaFit Application Controller

This directory connects the existing BananaFit account, fitness-intake, camera, equipment, and React modules. It does not replace those modules. `server.py` creates one FastAPI application and mounts their routes together so the current frontend can read authenticated plan data and live camera metrics from one origin.

## Responsibilities

The controller provides the application-facing data needed by the existing pages:

- Dashboard: today's plan, duration, exercise names, and a start-workout action.
- Progress: fourteen dated plan entries and today's exercise dose.
- Exercises: a Personal collection built from the signed-in user's current plan.
- Equipment Recognition: a start action that creates or resumes today's workout and opens Personal exercises.
- AI Coach: browser camera capture plus the latest form score, valid repetition count, warnings, and stream state from the current pose tracker.
- Plan lifecycle: expired fourteen-day plans send the user back through a new intake session. A newly generated plan becomes current and older plans remain as stale history.

The controller never accepts a user ID from the browser. Every private lookup derives the user from the signed, HTTP-only login cookie and applies the existing ownership checks.

## Existing structure used

```text
server.py                         one FastAPI process and camera streams
controller/
  router.py                      application-facing HTTP endpoints
  exercise_bridge.py             explicit plan-ID to exercise-library mapping
  runtime.py                     thread-safe latest camera metric snapshot
  workouts.py                    durable workout-session persistence
user_accounts/                   login, registration, CSRF, ownership, plan access
fitness_intake/                  YAML-driven intake and 14-day AI plan generation
frontend/                        existing React UI with data/button wiring only
data/sexybanana.db               local runtime SQLite database (created automatically)
```

`data/sexybanana.db` is runtime data and is intentionally ignored by Git. A production deployment should place the database on persistent storage by setting `SEXYBANANA_DATABASE_PATH`. Do not commit a database containing user data.

## Database relationships

The existing account migrations create:

- `users`: account identity and Argon2 password hash.
- `auth_sessions`: hashed login-session tokens.
- `fitness_session_owners`: ownership link between a user and an intake session.
- `workout_plans`: a generated plan linked to both the user and the owned intake session.

The controller adds:

- `workout_runtime_sessions`: one resumable runtime record for a user, plan, and plan day.
- `workout_set_results`: per-set valid/rejected repetitions, optional load, and form score.

The important association is:

```text
users.id
  -> fitness_session_owners.user_id
  -> workout_plans.user_id + workout_plans.fitness_session_id
  -> workout_runtime_sessions.user_id + workout_runtime_sessions.workout_plan_id
  -> workout_set_results.workout_session_id
```

Foreign keys and server-side `user_id` filters prevent one signed-in user from retrieving another user's plan or workout by changing a URL.

## Public plan response for the frontend

Use `GET /api/plans/current` when another frontend module needs the complete safe plan. Use `GET /api/app/today` for the page-ready version of today's plan.

Example `GET /api/app/today` response:

```json
{
  "status": "available",
  "plan_id": "userplan_...",
  "day": {
    "plan_id": "userplan_...",
    "plan_day": 1,
    "date": "2026-09-13",
    "kind": "training",
    "objective": "Comfortable full-body practice",
    "total_minutes": 18,
    "completed": false,
    "completed_count": 0,
    "exercise_count": 3,
    "exercises": [
      {
        "plan_exercise_id": "wall_pushup",
        "name": "Wall push-up",
        "phase": "main",
        "sets": 2,
        "repetitions": 8,
        "rest_seconds_between_sets": 60,
        "tempo_seconds_per_rep": 4,
        "rpe": 3,
        "completion_rule": "repetitions",
        "load_label": "Bodyweight",
        "coaching_cues": ["Use a comfortable stance."]
      }
    ]
  }
}
```

The frontend should treat `status` as authoritative:

- `available`: render plan data.
- `none`: the user has not generated a plan.
- `stale`: profile changes invalidated the plan; send the user to `/intake`.
- `expired`: the fourteen-day date range ended; send the user to `/intake`.

The plan generator does not invent numeric weights. `load_type` and `load_label` describe bodyweight, no load, resistance band, or a familiar comfortable load. A numeric `load_kg` may later be recorded as user-entered workout history.

## Application endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| GET | `/api/health` | No | Verify that the unified backend started. |
| GET | `/api/app/bootstrap` | Yes | Return the signed-in user, plan state, and today's page data. |
| GET | `/api/app/today` | Yes | Return today's plan and detailed exercise dose. |
| GET | `/api/app/calendar` | Yes | Return the plan's dated fourteen-day calendar. |
| GET | `/api/app/personal` | Yes | Return Personal-tab exercises for today's plan. |
| POST | `/api/workouts/today/start` | Yes + CSRF | Create or resume today's owned workout session. |
| GET | `/api/workouts/{workout_id}` | Yes | Read an owned workout runtime record. |
| POST | `/api/coach/frame` | No | Score one bounded browser-captured JPEG in memory without storing it. |
| GET | `/api/coach/metrics` | No | Read the latest non-sensitive pose score snapshot. |
| GET | `/video_feed` | No | Existing annotated pose MJPEG stream. |
| GET | `/equipment_feed` | No | Existing equipment-recognition MJPEG stream. |

All existing account, questionnaire, and plan endpoints remain available under `/api/auth`, `/api/intake`, and `/api/plans`.

## Frontend wiring

`frontend/src/api.js` sends same-origin requests with cookies. `frontend/vite.config.js` proxies backend paths to port 8000 during development. The visual structure and existing CSS classes remain unchanged; the wiring updates only the values or navigation targets that need to react to backend state.

- Dashboard and Progress load `/api/app/today`.
- Progress loads `/api/app/calendar` and marks planned, completed, and current dates with state classes.
- Personal loads `/api/app/personal`.
- Dashboard and Equipment start buttons call `/api/workouts/today/start` and navigate to `?page=exercises&tab=personal`.
- AI Coach asks the browser for camera permission, displays the browser stream, and sends a reduced JPEG frame to `/api/coach/frame` four times per second. The number and circular progress ring use only `CurlTracker.last_rep_score`, the same completed-repetition score rendered as `LAST xx%` by the existing camera HUD. Until the tracker completes a valid repetition, the UI shows no score. The endpoint uses a CPU-safe Ultralytics pose adapter, maps its COCO joints into the MediaPipe-shaped landmark contract already consumed by `pose/analyzer.py`, and then calls the existing curl tracker. This avoids the native MediaPipe Metal graph crash seen when a macOS web server has no graphical context. The other metric rows remain unchanged until their individual detectors exist.

On the first AI Coach frame, Ultralytics downloads `yolo11n-pose.pt` (about 6 MB) if it is not already in its model cache. The repository ignores `*.pt`, so downloaded weights are runtime data and are never part of a commit.

The public exercise catalog remains visible without a login. Private plan requests return 401; the page can still show its existing public fallback content.

## Detailed AI plan contract

The fitness-intake prompt and validation now require:

- exactly fourteen ordered days;
- a title and focus labels for every training day;
- warm-up, main, and cooldown phases;
- completion rule, load type, and coaching cues for every block;
- sets, repetitions, seconds of rest between sets, and seconds per repetition for strength work;
- explicit active minutes, rest minutes, RPE, equipment, and instructions;
- no numeric external load invented by the model;
- no automatic Week 2 increase before feedback.

Model output is parsed into the strict Pydantic schema, normalized for timing arithmetic, validated against readiness and the fixed exercise catalog, and only then stored for the authenticated user.

## Run locally

From the repository root, create a Python environment and install the packages listed by the existing components plus the camera dependencies. Then run:

```bash
python server.py
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. Account pages are served by the backend at `http://127.0.0.1:8000/register`, `/login`, and `/intake`.

The default development database is `data/sexybanana.db`. To use a different location:

```bash
export SEXYBANANA_DATABASE_PATH=/absolute/persistent/path/bananafit.db
```

The existing AI provider configuration is read by `fitness_intake`; environment variables can override its development configuration. The browser must explicitly select the AI-processing consent checkbox before plan generation.

The backend binds to `127.0.0.1:8000` by default. Deployment scripts can set
`BANANAFIT_HOST` and `BANANAFIT_PORT`. Camera capture is requested by the browser on the secure
`localhost`/`127.0.0.1` origin, so the Python process does not need direct macOS camera permission.
Captured frames are held only long enough to calculate pose metrics and are never written to the
database. If browser permission is denied, the existing camera panel shows its offline state.

## Verification

Run the component suites from their directories because each component owns its Python import path:

```bash
cd fitness_intake && python -m pytest -q
cd ../user_accounts && python -m pytest -q
cd .. && PYTHONPATH=.:fitness_intake/src:user_accounts/src python -m pytest -q controller/tests
cd frontend && npm run build
```

The controller tests cover explicit exercise mapping, safe no-animation fallback, camera-score updates, idempotent workout start, and cross-user workout isolation. The account suite covers registration, login, CSRF, URL ownership checks, questionnaire flow, user-plan association, and plan lifecycle. The intake suite covers the strict fourteen-day generation contract and rule validation.

## Integration rules

When extending the application:

1. Read identity only from `AccountService.authenticate`; do not accept `user_id` query or body fields.
2. Use `AccountService.get_current_plan_for_user` for private plan access.
3. Add exercise mappings explicitly in `EXERCISE_BRIDGE`; never guess a library animation at runtime.
4. Keep camera frames out of the database. Persist only derived workout results that the product needs.
5. Require CSRF validation for every cookie-authenticated mutation.
6. Keep old plans as history and use the newest available plan as the current plan.
7. Add new visual metrics only after a detector produces that metric; do not animate placeholder numbers as if they were measurements.
