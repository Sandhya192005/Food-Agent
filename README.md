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

### Storing meal photos in AWS S3

By default photos are saved in `media/`. To save new photos in S3 instead:

1. **Create a bucket** (S3 console → Create bucket). Keep **Block all public
   access** on: the app never makes photos public.
2. **Create an IAM user** for the app (IAM → Users → Create user) and attach this
   policy, so its keys can only touch that one bucket:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
       },
       {
         "Effect": "Allow",
         "Action": "s3:ListBucket",
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME"
       }
     ]
   }
   ```

   `ListBucket` lets S3 answer "no such file" for a deleted photo; without it S3
   answers "access denied" instead.

3. Create an **access key** for that user (Security credentials → Create access key
   → "Application running outside AWS"). Copy the secret now: AWS shows it only once.
4. Put these in `.env` (never in `.env.example` or code) and restart the backend:

   ```
   STORAGE_BACKEND=s3
   S3_BUCKET_NAME=your-bucket-name
   AWS_REGION=ap-southeast-2
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```

   `AWS_REGION` must be the bucket's region, as shown in the S3 bucket list.
   A wrong region still uploads, but the photo links fail with "400 Bad Request".

5. Check the connection. It uploads a test file, reads it back, opens its link and
   deletes it:

   ```powershell
   $env:PYTHONPATH = "."
   .\.venv\Scripts\python -c "import urllib.request; from app.services.storage.s3 import S3Storage; s=S3Storage(); k=s.save(b'hello','t.txt',folder='connection-test'); print(s.read(k), urllib.request.urlopen(s.url_for(k)).status); s.delete(k)"
   ```

   It works if it prints `b'hello' 200`.

How it works:

- **Upload:** each photo goes to `meals/user-<id>/<random>.jpg` in the bucket.
- **Database:** that object key goes in `meals.image_key`, and `meals.image_storage` records `s3`.
- **Viewing:** `GET /meals/{id}` returns `image_url`, a presigned link that works for 15 minutes, and the browser loads the photo straight from S3.
- **Fallback:** `GET /meals/{id}/image` serves the photo through the API.
- **Delete:** deleting a meal also deletes its photo from S3.
- **Older photos:** photos saved before the switch stay in `media/` (`image_storage = local`) and still show.
- **Code:** `app/services/storage/s3.py` uses boto3 (`put_object`, `get_object`,
  `delete_object`, `generate_presigned_url`). Tests use moto, a fake S3, so they
  need no AWS account.

To go back to local photos, set `STORAGE_BACKEND=local` and restart. An empty bucket
costs nothing; S3 only charges for stored files and requests.

### Using AWS RDS for the database

The app works with any PostgreSQL, so moving the database to AWS RDS needs no code
change, only a new `DATABASE_URL`. The engine uses `pool_pre_ping`, so it reconnects
quietly when RDS closes idle connections.

1. **Create the database** (RDS → Create database → **Full configuration**; *Easy
   create* turns public access off):

   | Setting | Choose |
   |---|---|
   | Engine | PostgreSQL (not Aurora), latest version |
   | Template | Free tier |
   | DB instance identifier | `food-agent-db` |
   | Credentials | Self managed, your own master password |
   | Instance class | Burstable → `db.t4g.micro` |
   | Storage | gp2, 20 GiB, storage autoscaling **off** |
   | Multi-AZ | No |
   | Public access | **Yes**, so your laptop can connect |
   | VPC security group | Create new: `food-agent-db-sg` |
   | RDS Extended Support, RDS Proxy, Enhanced Monitoring, log exports | Off |
   | Additional configuration → Initial database name | **`food_agent_db`** (without it, no database is created) |
   | Deletion protection | Off |

   For the password, use only letters, numbers, `-` and `_`: characters like
   `@ : / # ? %` break the `DATABASE_URL` line.

2. **Allow only your computer.** Once the status is *Available*, open the database →
   **Connectivity & security** → the security group → **Inbound rules**: type
   PostgreSQL, port 5432, source **My IP**. Never use `0.0.0.0/0`. If you later
   can't connect, your IP has probably changed: set **My IP** again.

3. **Point the app at it.** Copy the **Endpoint** from the same tab and set in `.env`
   (comment out the old line to switch back later):

   ```
   DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@YOUR_ENDPOINT:5432/food_agent_db?sslmode=require
   ```

   `sslmode=require` encrypts the connection between your laptop and AWS.

4. **Create the tables** and restart the backend:

   ```powershell
   $env:PYTHONPATH = "."
   .\.venv\Scripts\python -m alembic upgrade head
   ```

   The RDS database starts empty, so sign up again in the app. To copy existing
   local data instead, skip this step and run:

   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -h localhost -U postgres -d food_agent_db -Fc -f food_agent.dump
   & "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -h YOUR_ENDPOINT -U postgres -d food_agent_db --no-owner food_agent.dump
   ```

5. **See the data.** The AWS console doesn't show table rows. Connect pgAdmin
   (Register → Server: host = endpoint, port 5432, database `food_agent_db`, user
   `postgres`, SSL mode *require*) or `psql`.

**Cost:** unlike S3, RDS is charged for every hour it runs, even when empty and
unused. When you're not using it, **Stop** it (Actions → Stop temporarily; AWS
restarts it after 7 days). When you're done, **Delete** it: untick *Create final
snapshot* and *Retain automated backups*, then check RDS → Snapshots is empty. To
go back to your local database, restore your old `DATABASE_URL` line and restart.

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
