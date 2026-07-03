"""Rate limiting via slowapi.

Keying strategy: authenticated requests are limited *per session token* (we use
the tail of the Bearer token — stable per login, no JWT decode needed); requests
without a token (login / signup) fall back to the client IP.

Storage: in-process by default. When `REDIS_URL` is set the counters live in
Redis, so the limit is shared across the web process and any extra workers/
replicas instead of being per-process.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_key(request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            # Tail is plenty to distinguish sessions and keeps the key short.
            return f"user:{token[-40:]}"
    return f"ip:{get_remote_address(request)}"


_storage_uri = os.getenv("REDIS_URL") or "memory://"

limiter = Limiter(
    key_func=_rate_key,
    storage_uri=_storage_uri,
    headers_enabled=True,  # emit X-RateLimit-* headers
)

# Tunable limits (env-overridable) — defaults match ARCHITECTURE §11.7.
LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "5/minute")
LIMIT_GENERATE = os.getenv("RATE_LIMIT_GENERATE", "5/minute")
LIMIT_QUERY = os.getenv("RATE_LIMIT_QUERY", "30/minute")
LIMIT_JOBS = os.getenv("RATE_LIMIT_JOBS", "120/minute")  # polling is frequent by design
