# Implementation Notes

This document records the features added in this release (background processing,
rate limiting, auth hardening, frontend polish) and is the single place that
explains **how to run the whole project locally**. For shipping it to the
internet, see [`DEPLOYMENT.md`](./DEPLOYMENT.md); for the architectural tour of
the existing system, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## 1. What was implemented

### 1.1 Background processing — Redis + RQ

The two long LLM workflows no longer run inside the HTTP request. They are
enqueued as jobs and the client polls for the result.

- **`POST /api/generate-initial-report`** and **`POST /api/generate-final-report`**
  now return **`202 { "job_id": "...", "status": "queued" }`**.
- **`GET /api/jobs/{job_id}`** returns the job's `status`
  (`queued | started | finished | failed`), `progress` (0–100), a human `stage`
  label, and — when finished — the full `result` payload.

| File | Role |
|------|------|
| `server/jobs.py` | Redis/RQ queue factory **and** the Supabase `jobs`-table helpers (`create_job` / `update_job` / `get_job`). |
| `server/tasks.py` | The job functions the worker runs: `run_initial_report_job`, `run_final_report_job`. They write progress into the `jobs` row as they go. |
| `server/worker.py` | RQ worker entrypoint (`python worker.py`). |
| `server/extractors.py` | `extract_missing_fields` / `extract_quality_assessment` moved out of `main.py` so the worker can import them without booting FastAPI. |

**Design note:** job *state* is stored in the Supabase **`jobs` table**, not in
Redis. Redis is only the broker. This makes polling a plain RLS-scoped DB read,
keeps the API contract simple, and means progress survives a worker restart.

**No-Redis fallback:** if `REDIS_URL` is unset, the API runs the job in a
background thread in-process using the *same* job-based contract (submit → poll).
Great for local dev; single-instance only, and jobs are lost on restart — so set
`REDIS_URL` for anything real.

### 1.2 Rate limiting — slowapi

`server/rate_limit.py` adds a limiter keyed per session token (falling back to
client IP for unauthenticated calls). Counters live in Redis when `REDIS_URL` is
set, otherwise in-process memory.

| Route group | Default limit | Env override |
|-------------|---------------|--------------|
| `/api/auth/login`, `/signup`, `/refresh` | `5/minute` | `RATE_LIMIT_AUTH` |
| `/api/generate-*` | `5/minute` | `RATE_LIMIT_GENERATE` |
| `/api/rag/query`, `/api/download-pdf` | `30/minute` | `RATE_LIMIT_QUERY` |
| `/api/jobs/{id}` | `120/minute` | `RATE_LIMIT_JOBS` |

Exceeding a limit returns **HTTP 429** with a `Retry-After` header; the frontend
surfaces a friendly "slow down" message.

### 1.3 Authentication hardening (pragmatic)

- **Refresh-token rotation.** `login` / `signup` now return `refresh_token` and
  `expires_at` alongside the access token. New **`POST /api/auth/refresh`**
  exchanges a refresh token for a fresh pair (Supabase rotates the refresh token
  on every call).
- **Silent + reactive refresh (frontend).** `AuthContext` schedules a refresh
  ~60 s before the access token expires, and on any `401` it transparently
  refreshes once and replays the original request before giving up.
- **Security headers.** Every response carries `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a tight
  `Content-Security-Policy`. `Strict-Transport-Security` is opt-in via
  `ENABLE_HSTS=true` (enable only when served over TLS).

> JWTs still live in `localStorage` (per the chosen "pragmatic" scope). A full
> HttpOnly-cookie + CSRF migration remains a future option (ARCHITECTURE §11.8).

### 1.4 Frontend polish

- **Live job progress.** The Dashboard renders a real progress bar with the
  job's current stage label (e.g. *"reading drawing (vision)"*) and percentage,
  driven by `pollJob` in `client/src/api.js`.
- **429 handling.** Rate-limit responses become a readable message instead of a
  raw error.
- **Storybook.** `client/.storybook/` config + stories for `FileUpload`,
  `ReportDisplay`, and `Sidebar` (`npm run storybook`).

---

## 2. New / changed files at a glance

```
server/
├── jobs.py          (new)  RQ queue + Supabase jobs-table helpers
├── tasks.py         (new)  worker job functions
├── worker.py        (new)  RQ worker entrypoint
├── extractors.py    (new)  report parsers (moved out of main.py)
├── rate_limit.py    (new)  slowapi limiter + limits
├── Dockerfile       (new)  API + worker image (honcho)
├── Procfile         (new)  web + worker process definitions
├── .env.example     (new)  every env var, documented
├── db/migrations.sql(new)  the `jobs` table DDL
├── main.py        (edit)  routes enqueue jobs; +/api/jobs/{id}; security headers; rate limits
├── auth.py        (edit)  refresh token + /api/auth/refresh + auth rate limit
└── pyproject.toml (edit)  + slowapi, redis, rq, honcho

client/
├── .storybook/                       (new)  Storybook 9 config
├── src/stories/decorators.jsx        (new)  Router+Auth decorator
├── src/components/*.stories.jsx       (new)  3 component stories
├── src/api.js                        (edit) job submit/poll, refreshSession, 429 text
├── src/context/AuthContext.jsx       (edit) silent + reactive token refresh
├── src/pages/DashboardPage.jsx       (edit) submit→poll + progress UI
└── package.json                      (edit) Storybook deps + scripts

root/
├── DEPLOYMENT.md    (new)  free-first deploy guide
├── IMPLEMENTATION.md(new)  this file
└── render.yaml      (new)  Render blueprint (alternative deploy)
```

---

## 3. Running locally

### 3.1 Prerequisites
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pip)
- Node.js 20+ / npm
- An OpenAI API key and a Supabase project (URL + anon key + service-role key)
- **Optional:** Docker (for Redis). Without Redis the app still runs — jobs
  execute in-process.

### 3.2 Supabase tables (one-time)
In the Supabase SQL editor, create the `reports` table (see `README.md`) **and**
run the new jobs migration:

```bash
# contents of server/db/migrations.sql  → paste into the Supabase SQL editor
```

### 3.3 Redis (optional but recommended)
```bash
docker run -d -p 6379:6379 redis:7-alpine
# then set REDIS_URL=redis://localhost:6379/0 in server/.env
```
Skip this to use the in-process fallback (leave `REDIS_URL` unset).

### 3.4 Backend
```bash
cd server
cp .env.example .env          # fill in OPENAI_API_KEY + the 3 Supabase keys
uv sync                       # or: pip install -e .

# One-time: clean source markdown + build the RAG vector index
uv run python clean_docs.py
uv run python ingest.py --rebuild

# Start the API + worker together (honcho reads the Procfile):
uv run honcho start

#  …or run them in two terminals:
#  Terminal A:  uv run uvicorn main:app --reload --port 8000
#  Terminal B:  uv run python worker.py     # only needed if REDIS_URL is set
```
> On Windows, also set `RQ_SIMPLE_WORKER=1` in `.env` (the worker can't fork).

The API is at `http://localhost:8000` (interactive docs at `/docs`).

### 3.5 Frontend
```bash
cd client
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm install
npm run dev                   # app at http://localhost:5173
npm run storybook             # component workshop at http://localhost:6006
```

### 3.6 Smoke test the flow
1. Open `http://localhost:5173`, sign up / log in.
2. Upload a drawing → you'll see the **progress bar advance** as the background
   job classifies → reads → extracts.
3. Fill missing fields (or type `assume`) → final RAG verdict streams in via the
   same job-polling mechanism.
4. Download `.md` / `.pdf`; revisit under **History**.

---

## 4. Verifying the backend without a full install

The modules byte-compile and import cleanly. Quick checks:

```bash
cd server
python -m py_compile main.py auth.py jobs.py tasks.py worker.py extractors.py rate_limit.py
# With deps installed (uv sync):
uv run python -c "import main; print(len(main.app.routes), 'routes')"
```

---

## 5. API contract changes (breaking)

If anything other than this repo's frontend calls the API, note:

| Endpoint | Before | After |
|----------|--------|-------|
| `POST /api/generate-initial-report` | `200` full report JSON | **`202 { job_id }`** — poll `GET /api/jobs/{id}` |
| `POST /api/generate-final-report` | `200` full report JSON | **`202 { job_id }`** — poll `GET /api/jobs/{id}` |
| `GET /api/jobs/{id}` | — | **new** — job status + result |
| `POST /api/auth/login` / `/signup` | `{ access_token, user_id, email }` | **+ `refresh_token`, `expires_at`** |
| `POST /api/auth/refresh` | — | **new** — rotate tokens |

The finished job's `result` payload is exactly the JSON the old synchronous
endpoints used to return, so downstream parsing only needs to move behind the
poll.
