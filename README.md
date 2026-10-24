# AI Food Agent

FastAPI backend for a personal nutrition assistant: profile-aware food photo analysis
(OpenAI vision), a recurring office-menu shortcut for logging meals without a photo,
water tracking, and AI-generated nutrition recommendations (OpenAI text).

See [ARCHITECTURE.md](./ARCHITECTURE.md) for how the pieces fit together, the database
schema, and the key design decisions behind them.

## Features

- **Auth & profile**: JWT auth (signup/login/refresh/logout) with a full nutrition
  profile at signup (age, gender, height, weight, medical conditions, goal, diet
  preference, activity level, food budget, timezone). BMI, BMR, TDEE, and a daily
  water goal are computed automatically and recomputed whenever
  weight/height/age/gender/activity level change.
- **Food photo analysis** via OpenAI vision: detects items, estimates quantity,
  calories, protein, and fat; flags low-confidence detections; caps unrealistic
  calorie estimates; deduplicates repeat uploads of the same image within a
  configurable window.
- **Recurring office menu**: admins define a fixed weekly menu (day + meal type →
  dish + nutrition). Clients can poll `GET /menu/today-prompt` for a Yes/No question
  ("Today is Tuesday, is your lunch going to be Sambar with Potato?") and log the
  meal instantly via `POST /meals/confirm-from-menu` — no photo or AI call needed. A
  "No" answer falls back to the normal photo-upload flow.
- **Water intake logging** with an on-demand reminder endpoint (client polls it) and
  a snooze action.
- **AI nutrition recommendations** that respect diet preference, medical conditions,
  and food budget, generated from the user's profile, meal history, and hydration
  progress.
- **Audit trail**: every table tracks `created_by`/`updated_by`/`deleted_at`/
  `deleted_by`; deletes are soft (rows are marked inactive, not erased) so history
  stays queryable.

## Setup

1. Copy `.env.example` to `.env` and fill in real values — at minimum `SECRET_KEY`
   (any long random string) and `OPENAI_API_KEY` (your OpenAI key).
2. Choose a database — `DATABASE_URL` in `.env` supports either:
   - SQLite (zero setup): `sqlite:///./data/food_agent.db` (the default)
   - PostgreSQL: `postgresql+psycopg2://user:password@localhost:5432/food_agent_db`
     — create the database/role yourself first (`CREATE DATABASE`, `CREATE ROLE ...
     LOGIN PASSWORD ...`); the app doesn't create it for you.
3. Create a virtual environment and install dependencies:

   ```
   python -m venv .venv
   .venv/Scripts/activate       # Windows
   pip install -r requirements-dev.txt
   ```

4. Apply database migrations:

   ```
   alembic upgrade head
   ```

5. Run the API:

   ```
   uvicorn app.main:app --reload --reload-dir app
   ```

   (`--reload-dir app` scopes the file watcher to your source code — without it,
   `--reload` also watches `.venv`, which is slow and noisy.)

6. Open `http://127.0.0.1:8000/docs` for interactive Swagger UI. Click **Authorize**
   and paste an access token (from a signup/login response) to unlock protected
   endpoints.

### Running the web frontend

The React app lives in `frontend/` (Vite + TypeScript). With the API running on
port 8000, in a second terminal:

```
cd frontend
npm install        # first time only
npm run dev
```

Open `http://127.0.0.1:5173`. The dev server forwards `/api` calls to the backend,
so no CORS setup is needed. Pages: Today (dashboard), Log meal (photo upload),
Meals, Office menu, Water, Suggestions and Profile. The 🔔 bell shows the water and
meal agents' reminders, checking every 30 seconds.

`npm run build` type-checks and produces a production build in `frontend/dist/`.

### Making an account an admin

Only admins can create/edit/delete the recurring weekly menu (`PUT`/`DELETE
/menu/weekly`). There is no signup field or endpoint for this — by design, no user
can grant themselves admin through the API. Promote an account by running SQL
directly against the database:

```sql
UPDATE users SET is_admin = true WHERE email = 'someone@example.com';
```

## Running with Docker

```
docker-compose up --build
```

This runs migrations automatically on container start and serves the API on
`http://localhost:8000`. **Note:** `docker-compose.yml` is currently wired for
SQLite only (bind-mounted to `./data` on the host) — it has not been updated for
PostgreSQL. If you want to run Docker against Postgres, `docker-compose.yml` needs
a `DATABASE_URL` override (and, if you want Postgres itself containerized, a `db`
service added). Because SQLite is a single-writer file database, the SQLite path
must be run as a single replica regardless.

## Tests

```
pytest --cov
```

Tests always run against a throwaway SQLite database (`tests/conftest.py`),
regardless of what `DATABASE_URL` points to in your `.env` — they never touch your
real database. The real OpenAI API is never called either — the vision and
recommendation service functions are mocked at the boundary.

## Project layout

- `app/models/` — SQLAlchemy ORM models (DB shape): `user.py`, `meal.py`, `menu.py`
  (weekly menu templates), `water.py`, `recommendation.py`
- `app/schemas/` — Pydantic request/response models (API contract)
- `app/services/` — business logic, framework-agnostic: BMI/BMR/TDEE math
  (`health_metrics.py`), water goals (`water_goals.py`), meal validation
  (`meal_validation.py`), weekly menu + today-prompt logic (`menu_service.py`),
  storage abstraction (`storage/`), OpenAI integration (`ai/`)
- `app/api/v1/` — FastAPI routers, one per resource (`auth`, `users`, `meals`,
  `menu`, `water`, `recommendations`)
- `app/api/deps.py` — shared auth dependencies (`get_current_user`,
  `get_current_admin_user`)
- `alembic/` — database migrations, applied in order; see `ARCHITECTURE.md` for
  what each one changed and why

## Extending

New AI-driven features (grocery planning, wearable integration, health coaching)
should follow the pattern in `app/services/ai/recommendation_service.py`: a
`build_context()` function that assembles a typed context dict, a prompt template in
`app/services/ai/prompts.py`, and a `generate_*()` function that calls
`app/services/ai/openai_client.py` and returns a typed result — reusing the existing
error-handling/timeout/retry plumbing rather than duplicating it.

New admin-only features should reuse `get_current_admin_user` (`app/api/deps.py`)
rather than re-checking `current_user.is_admin` inline in a router.
