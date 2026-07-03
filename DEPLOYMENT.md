# Deployment Guide

This guide deploys the full stack — React SPA, FastAPI API, an RQ background
worker, Redis, ChromaDB, and Supabase — with a **free-first** bias. Every
component below has a working free tier **except the OpenAI API**, which is the
one unavoidable cost (the product is built around GPT-4o vision + o4-mini
reasoning; there is no free substitute for those). That charge is quantified in
[§7](#7-the-one-real-cost-openai).

> TL;DR of the free path: **Cloudflare Pages** (frontend) + **Hugging Face
> Docker Space** (API + worker in one box) + **Upstash Redis** + **Supabase** —
> all free. You pay only OpenAI usage.

---

## 1. What has to run

| Component | What it does | Notes |
|-----------|--------------|-------|
| **Frontend** | React 19 SPA (static files) | Trivially free anywhere. |
| **API (web)** | FastAPI: auth, uploads, enqueues jobs, serves job status | Light memory — does **not** load the ML models. |
| **Worker** | RQ worker: runs the vision + RAG + reasoning pipeline | **Heavy** — loads torch + BGE-large (1.3 GB) + reranker (280 MB) + ChromaDB. Needs ~2–3 GB RAM. |
| **Redis** | RQ broker + (optional) rate-limit counters | Job *state* lives in Supabase, not Redis, so Redis traffic stays low. |
| **Supabase** | Postgres + Auth (JWT) + the `reports`/`jobs` tables | Free tier is generous. |
| **OpenAI** | gpt-4o / gpt-4o-mini / o4-mini | **Paid.** See §7. |

The web and worker run from the **same Docker image** (`server/Dockerfile`),
started together by `honcho` (`server/Procfile`). That lets a *single* free
container host both — which is what makes the all-free path possible.

---

## 2. Free-service matrix

| Need | Free option | Free-tier limit | Verdict |
|------|-------------|-----------------|---------|
| Static frontend | **Cloudflare Pages** / Vercel / Netlify | unlimited static, generous bandwidth | ✅ truly free |
| API + worker (≈2–3 GB RAM) | **Hugging Face Docker Space (CPU basic)** | **16 GB RAM, 2 vCPU**, sleeps after 48 h idle | ✅ free, best fit for the ML models |
| Redis | **Upstash Redis** | 10 000 commands/day, 256 MB | ✅ free (see §6 on staying under budget) |
| Postgres + Auth | **Supabase** | 500 MB DB, 50 k MAU | ✅ free |
| Vector store | **ChromaDB** (embedded, baked into the image) | n/a — ships in the container | ✅ free |
| LLM calls | OpenAI | — | 💲 **paid, unavoidable** |

**Why Hugging Face Spaces and not Render/Railway/Fly free?** The worker needs
~2–3 GB RAM for the local embedding + reranker models. Render's free web service
is 512 MB; Fly.io's free shared VMs are ~256 MB; Render background workers are a
paid feature entirely. Hugging Face Spaces gives **16 GB free**, which is the
only mainstream free tier that fits the models as-is. If you would rather use
Render/Fly free, see [§5](#5-alternative-fit-the-backend-into-512-mb) — it swaps
the local models for OpenAI embeddings so the backend fits in 512 MB (at a tiny
extra OpenAI cost and slightly lower retrieval quality).

---

## 3. One-time setup (shared by all paths)

### 3.1 Supabase
1. Create a free project at <https://supabase.com>.
2. Run **both** migrations in the SQL editor:
   - the `reports` table (see `ARCHITECTURE.md` §5), if not already created;
   - `server/db/migrations.sql` — the new **`jobs`** table for background jobs.
3. Copy from *Project Settings → API*: `SUPABASE_URL`, the **anon** key
   (`SUPABASE_KEY`), and the **service-role** key (`SUPABASE_SERVICE_ROLE_KEY`).

### 3.2 Upstash Redis
1. Create a free database at <https://upstash.com>.
2. Copy the **`rediss://` TLS** connection URL → this is `REDIS_URL`.

### 3.3 OpenAI
1. Create an API key at <https://platform.openai.com>.
2. **Set a hard monthly spend limit** (Billing → Limits) so a runaway loop can't
   surprise you. → `OPENAI_API_KEY`.

---

## 4. Recommended free path (Hugging Face Spaces + Cloudflare Pages)

### 4.1 Backend → Hugging Face Docker Space
1. Create a new **Space** → SDK: **Docker** → hardware: **CPU basic (free)**.
2. Push the `server/` directory to the Space repo (it contains the `Dockerfile`,
   `Procfile`, and `worker.py`). In the Space **README** front-matter set
   `app_port: 7860` (the Dockerfile already listens there).
3. In *Settings → Variables and secrets*, add everything from
   `server/.env.example` that matters in prod — at minimum:
   ```
   OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY,
   REDIS_URL, CORS_ALLOW_ORIGINS (your Pages URL), ENABLE_HSTS=true
   ```
   On a single-core Space also set `RQ_SIMPLE_WORKER=1` so the worker doesn't try
   to fork.
4. The image build runs `python ingest.py`, baking the ChromaDB index **and** the
   BGE model cache into the image, so the first job doesn't pay a cold download.
5. `honcho start` boots `uvicorn` + the RQ `worker` together. Done.

> Caveat: free Spaces **sleep after 48 h of inactivity** and cold-start takes
> ~30–60 s while the models load. Fine for a demo/portfolio; not for SLA traffic.

### 4.2 Frontend → Cloudflare Pages
1. Connect the repo, set the build root to `client/`.
2. Build command `npm run build`, output dir `dist`.
3. Env var: `VITE_API_BASE_URL = https://<your-space>.hf.space`.
4. After it deploys, add the Pages URL to the backend's `CORS_ALLOW_ORIGINS` and
   redeploy the Space.

That's the whole free stack. Total recurring cost = OpenAI usage only.

---

## 5. Alternative: fit the backend into 512 MB

If you must use a 512 MB free tier (Render free web, Fly.io free, Koyeb free),
drop the local ML so the worker fits:

1. **Embeddings → OpenAI.** Replace the BGE embedder in
   `server/embedding_service.py` with `text-embedding-3-small` via the OpenAI
   client. Re-run `python ingest.py --rebuild` so the index uses the new vectors
   (1536-dim). Cost: ~$0.00002 / 1 K tokens — cents per full re-ingest.
2. **Reranker → off.** Set `RERANK_ENABLED=false` and `MMR_ENABLED=false`
   (MMR needs candidate embeddings). Retrieval quality drops modestly; the
   `rag_confidence_low` flag still works off raw scores.
3. Now `torch`/`sentence-transformers` are unused — the container fits in
   512 MB. Use `render.yaml` with `plan: free`.

Render background workers remain paid, so on Render free you'd run the worker in
the same web dyno via `honcho start` (as the Dockerfile does) rather than a
separate `worker:` service.

---

## 6. Staying inside Upstash's free command budget

Job **state** is stored in the Supabase `jobs` table, not Redis — so the
frontend's polling (`GET /api/jobs/{id}` every 2 s) hits **Postgres, not
Redis**. Redis only sees: enqueue, worker dequeue/heartbeat, and — if you point
slowapi at it — rate-limit counters.

To conserve the 10 000 commands/day:
- Keep rate-limit storage **in-process** (it already falls back to memory; only
  uses Redis if you deliberately share `REDIS_URL` with slowapi). On a single
  container, in-memory limits are correct anyway.
- The RQ worker heartbeats periodically; one idle worker is well within budget.

If you outgrow the free tier, Upstash bills per-request pennies — no fixed fee.

---

## 7. The one real cost: OpenAI

Everything else is free. OpenAI is not. Rough per-analysis estimate (one
drawing → initial report → final report), at list prices:

| Call | Model | Typical tokens | ~Cost |
|------|-------|----------------|-------|
| Classify | gpt-4o-mini | ~1 K in | <$0.001 |
| Vision extract | gpt-4o | ~3–8 K in (hi-detail image) + ~2 K out | ~$0.03–0.06 |
| Validate | gpt-4o-mini | ~1 K | <$0.001 |
| Final report | o4-mini (reasoning) | ~4–8 K in + reasoning + ~2 K out | ~$0.02–0.05 |

**≈ $0.05–0.12 per full analysis.** A few hundred analyses ≈ a few dollars.
Mitigations already in the codebase / recommended:
- Prompt caching is automatic on gpt-4o / o-series for the long static preambles
  (ARCHITECTURE §11.5) — keeps repeat calls cheaper.
- Set a **hard billing limit** in the OpenAI dashboard.
- The new rate limits (`5/min` on generate routes) cap worst-case spend per user.

---

## 8. Pre-flight checklist

- [ ] `jobs` table created in Supabase (`server/db/migrations.sql`).
- [ ] `reports` table exists with RLS (ARCHITECTURE §5).
- [ ] Backend env: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`,
      `SUPABASE_SERVICE_ROLE_KEY`, `REDIS_URL`, `CORS_ALLOW_ORIGINS`,
      `ENABLE_HSTS=true`.
- [ ] Frontend env: `VITE_API_BASE_URL` → backend URL.
- [ ] Frontend origin added to backend `CORS_ALLOW_ORIGINS`.
- [ ] OpenAI billing limit set.
- [ ] (Single-core host) `RQ_SIMPLE_WORKER=1`.

---

## 9. Local development

```bash
# 1. Redis (Docker) — or just leave REDIS_URL unset to run jobs in-process.
docker run -p 6379:6379 redis:7-alpine

# 2. Backend
cd server
cp .env.example .env            # fill in secrets
uv sync                         # or: pip install -e .
python ingest.py                # build the vector index once
honcho start                    # API + worker together
#   ...or run them separately:
#   uvicorn main:app --reload --port 8000
#   python worker.py

# 3. Frontend
cd client
npm install
npm run dev                     # http://localhost:5173
npm run storybook               # component workshop on :6006
```

**No Redis?** Leave `REDIS_URL` unset. The API then runs jobs in-process
(fire-and-forget in a thread) using the *same* job-based contract — the client
still submits a job and polls `GET /api/jobs/{id}`. Single instance only, and
jobs die on restart, so this is for local dev, not production.

---

## 10. What changed in this release

- **Background jobs (RQ).** `POST /api/generate-initial-report` and
  `/generate-final-report` now return `202 {job_id}` and the client polls
  `GET /api/jobs/{id}`. New files: `server/jobs.py`, `server/tasks.py`,
  `server/worker.py`. Report-parsing helpers moved to `server/extractors.py`.
- **Rate limiting.** slowapi on auth (5/min), generate (5/min), query/pdf
  (30/min), job polling (120/min). `server/rate_limit.py`.
- **Auth hardening.** Login/signup return a `refresh_token` + `expires_at`;
  new `POST /api/auth/refresh` rotates tokens; the SPA silently refreshes before
  expiry and replays a request once after a 401. Security headers
  (CSP/X-Frame-Options/Referrer-Policy, opt-in HSTS) on every response.
- **Frontend polish.** Live job-progress bar with stage labels, friendly 429
  handling, Storybook stories for `FileUpload`, `ReportDisplay`, `Sidebar`.
