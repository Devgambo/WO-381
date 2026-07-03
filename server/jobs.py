"""Background-job plumbing.

Two cooperating stores:

* **Redis + RQ** — the broker. `get_queue()` hands back the RQ queue that the
  web process enqueues onto and the `worker.py` process drains.
* **Supabase `jobs` table** — the *source of truth the client polls*. We do
  not expose Redis/RQ internals to the browser; instead every task writes its
  progress and result into a row that is RLS-scoped to the owning user. This
  survives worker restarts and keeps the polling endpoint a plain authenticated
  DB read.

See `DEPLOYMENT.md` for the `jobs` table DDL.
"""
import logging
import os
from datetime import datetime, timezone

from database import get_supabase_admin_client

log = logging.getLogger("compliance.jobs")

REDIS_URL = os.getenv("REDIS_URL")
JOB_QUEUE_NAME = os.getenv("JOB_QUEUE_NAME", "compliance")
JOB_TIMEOUT = int(os.getenv("JOB_TIMEOUT", "600"))  # seconds — vision + reasoning can be slow

_redis = None
_queue = None


def background_enabled() -> bool:
    return bool(REDIS_URL)


def get_redis():
    global _redis
    if _redis is None:
        if not REDIS_URL:
            raise RuntimeError("REDIS_URL must be set to use background jobs")
        from redis import Redis
        _redis = Redis.from_url(REDIS_URL)
    return _redis


def get_queue():
    global _queue
    if _queue is None:
        from rq import Queue
        _queue = Queue(JOB_QUEUE_NAME, connection=get_redis(), default_timeout=JOB_TIMEOUT)
    return _queue


# ---------------------------------------------------------------------------
# Supabase-backed job state (what the client polls)
# ---------------------------------------------------------------------------
def create_job(user_id: str, job_type: str, report_id: str | None = None) -> str:
    sb = get_supabase_admin_client()
    res = sb.table("jobs").insert({
        "user_id": user_id,
        "type": job_type,
        "status": "queued",
        "progress": 0,
        "report_id": report_id,
    }).execute()
    if not res.data:
        raise RuntimeError("Could not create job row")
    return res.data[0]["id"]


def update_job(job_id: str, **fields) -> None:
    """Patch a job row. Swallows DB errors so a transient blip never crashes a
    worker mid-task — the next update (or the terminal one) will reconcile."""
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        sb = get_supabase_admin_client()
        sb.table("jobs").update(fields).eq("id", job_id).execute()
    except Exception:
        log.exception("update_job failed for %s", job_id)


def get_job(job_id: str, user_id: str) -> dict | None:
    sb = get_supabase_admin_client()
    res = sb.table("jobs") \
        .select("id, type, status, progress, stage, result, error, report_id, created_at, updated_at") \
        .eq("id", job_id) \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    return res.data
