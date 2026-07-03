import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr

from database import get_supabase_client
from rate_limit import LIMIT_AUTH, limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Short in-process cache to avoid hammering Supabase on every authenticated
# request. Tokens still expire naturally; a stolen token gains at most TTL
# extra seconds of validity in-process — a trivial price for the latency win.
_USER_CACHE: dict[str, tuple[float, dict]] = {}
_USER_CACHE_TTL = float(os.getenv("SUPABASE_USER_CACHE_TTL", "60"))


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: Optional[EmailStr] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None  # unix seconds, when the access token expires


class RefreshRequest(BaseModel):
    refresh_token: str


def _parse_bearer(authorization: str) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")
    return parts[1].strip()


def _cache_get(token: str) -> dict | None:
    entry = _USER_CACHE.get(token)
    if not entry:
        return None
    ts, user = entry
    if time.monotonic() - ts > _USER_CACHE_TTL:
        _USER_CACHE.pop(token, None)
        return None
    return user


def _cache_put(token: str, user: dict) -> None:
    _USER_CACHE[token] = (time.monotonic(), user)
    # Keep the cache from growing unbounded under token churn.
    if len(_USER_CACHE) > 1024:
        cutoff = time.monotonic() - _USER_CACHE_TTL
        for k, (ts, _) in list(_USER_CACHE.items()):
            if ts < cutoff:
                _USER_CACHE.pop(k, None)


def _cache_invalidate(token: str) -> None:
    _USER_CACHE.pop(token, None)


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Validate the JWT from the Authorization header. Returns {'id', 'email', 'token'}."""
    token = _parse_bearer(authorization)

    cached = _cache_get(token)
    if cached is not None:
        return cached

    try:
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        user = user_response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    payload = {"id": str(user.id), "email": user.email or "", "token": token}
    _cache_put(token, payload)
    return payload


@router.post("/signup", response_model=AuthResponse)
@limiter.limit(LIMIT_AUTH)
async def signup(request: Request, body: AuthRequest):
    """Register a new user with email and password."""
    try:
        supabase = get_supabase_client()
        res = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
        })
        if not res.user:
            raise HTTPException(status_code=400, detail="Signup failed")
        session = res.session
        return AuthResponse(
            access_token=session.access_token if session else "",
            user_id=str(res.user.id),
            email=res.user.email,
            refresh_token=session.refresh_token if session else None,
            expires_at=session.expires_at if session else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
@limiter.limit(LIMIT_AUTH)
async def login(request: Request, body: AuthRequest):
    """Login with email and password."""
    try:
        supabase = get_supabase_client()
        res = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
        if not res.user or not res.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return AuthResponse(
            access_token=res.session.access_token,
            user_id=str(res.user.id),
            email=res.user.email,
            refresh_token=res.session.refresh_token,
            expires_at=res.session.expires_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit(LIMIT_AUTH)
async def refresh(request: Request, body: RefreshRequest):
    """Exchange a refresh token for a fresh access token.

    Supabase rotates the refresh token on every call, so the client must store
    the new `refresh_token` it gets back. The previous in-process auth cache
    entry for the *old* access token is left to expire naturally.
    """
    if not body.refresh_token.strip():
        raise HTTPException(status_code=400, detail="refresh_token is required")
    try:
        supabase = get_supabase_client()
        res = supabase.auth.refresh_session(body.refresh_token)
        if not res.session or not res.user:
            raise HTTPException(status_code=401, detail="Could not refresh session")
        return AuthResponse(
            access_token=res.session.access_token,
            user_id=str(res.user.id),
            email=res.user.email,
            refresh_token=res.session.refresh_token,
            expires_at=res.session.expires_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Could not refresh session")


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Invalidate the Supabase session for the supplied access token."""
    token = current_user["token"]
    _cache_invalidate(token)
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out(token)
    except Exception:
        # Token may already be expired/invalid — treat as already-signed-out.
        pass
    return {"message": "Logged out"}
