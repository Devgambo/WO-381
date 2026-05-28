from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr

from database import get_supabase_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: Optional[EmailStr] = None


def _parse_bearer(authorization: str) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")
    return parts[1].strip()


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Validate the JWT from the Authorization header. Returns {'id', 'email', 'token'}."""
    token = _parse_bearer(authorization)
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
    return {"id": str(user.id), "email": user.email or "", "token": token}


@router.post("/signup", response_model=AuthResponse)
async def signup(body: AuthRequest):
    """Register a new user with email and password."""
    try:
        supabase = get_supabase_client()
        res = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
        })
        if not res.user:
            raise HTTPException(status_code=400, detail="Signup failed")
        return AuthResponse(
            access_token=res.session.access_token if res.session else "",
            user_id=str(res.user.id),
            email=res.user.email,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest):
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
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Invalidate the Supabase session for the supplied access token."""
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out(current_user["token"])
    except Exception:
        # Token may already be expired/invalid — treat as already-signed-out.
        pass
    return {"message": "Logged out"}
