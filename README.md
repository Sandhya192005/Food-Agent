# AI Food Agent

FastAPI backend for a personal nutrition assistant: profile-aware food photo analysis
(OpenAI vision), water tracking, and AI-generated nutrition recommendations (OpenAI text).

## Features

- JWT auth (signup/login/refresh/logout) with a full nutrition profile at signup
  (age, gender, height, weight, medical conditions, goal, diet preference, activity
  level, food budget, timezone). BMI, BMR, TDEE, and a daily water goal are computed
  automatically and recomputed whenever weight/height/age/gender/activity level change.
- Food photo analysis via OpenAI vision: detects items, estimates quantity and
  calories, flags low-confidence detections, caps unrealistic calorie estimates, and
  deduplicates repeat uploads of the same image within a configurable window.
- Water intake logging with an on-demand reminder endpoint (client polls it) and a
  snooze action.
- AI nutrition recommendations that respect diet preference, medical conditions, and
  food budget, generated from the user's profile, meal history, and hydration progress.

## Setup

1. Copy `.env.example` to `.env` and fill in real values — at minimum `SECRET_KEY`
   (any long random string) and `OPENAI_API_KEY` (your OpenAI key).
2. Create a virtual environment and install dependencies:

   ```
   python -m venv .venv
   .venv/Scripts/activate       # Windows
   pip install -r requirements-dev.txt
   ```

3. Apply database migrations:

   ```
   alembic upgrade head
   ```

4. Run the API:

   ```
   uvicorn app.main:app --reload
   ```

5. Open `http://127.0.0.1:8000/docs` for interactive Swagger UI.

## Running with Docker

```
docker-compose up --build
```

This runs migrations automatically on container start and serves the API on
`http://localhost:8000`. The SQLite database file and uploaded images are bind-mounted
to `./data` and `./media` on the host, so they persist across container restarts.
Requires `.env` to exist (same as local setup) — `docker-compose.yml` reads it via
`env_file`. Because SQLite is a single-writer file database, this service must be run
as a single replica.

## Tests

```
pytest --cov
```

Tests never call the real OpenAI API — the vision and recommendation service
functions are mocked at the boundary. See `tests/conftest.py`.

## Project layout

- `app/models/` — SQLAlchemy ORM models (DB shape)
- `app/schemas/` — Pydantic request/response models (API contract)
- `app/services/` — business logic, framework-agnostic (BMI/BMR/TDEE math, water
  goals, meal validation, storage abstraction, OpenAI integration)
- `app/api/v1/` — FastAPI routers
- `alembic/` — database migrations

## Extending

New AI-driven features (grocery planning, wearable integration, health coaching)
should follow the pattern in `app/services/ai/recommendation_service.py`: a
`build_context()` function that assembles a typed context dict, a prompt template in
`app/services/ai/prompts.py`, and a `generate_*()` function that calls
`app/services/ai/openai_client.py` and returns a typed result — reusing the existing
error-handling/timeout/retry plumbing rather than duplicating it.
