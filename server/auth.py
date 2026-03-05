from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from database import get_supabase_client

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str


async def get_current_user(authorization: str = Header(...)) -> dict:
    """
    Dependency that validates the JWT from the Authorization header.
    Returns dict with 'id' and 'email'.
    """
    try:
        token = authorization.replace("Bearer ", "")
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"id": str(user.id), "email": user.email}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


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
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout the current user."""
    return {"message": "Logged out successfully"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Get the current user's info."""
    return current_user
