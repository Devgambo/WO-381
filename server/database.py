import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # anon key – used for auth
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service role – used for DB ops

_supabase_client: Client | None = None
_supabase_admin_client: Client | None = None


def get_supabase_client() -> Client:
    """Return the Supabase client initialised with the **anon** key.
    This is the correct client for user-facing auth operations
    (sign_up, sign_in_with_password, get_user, etc.)."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in .env"
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def get_supabase_admin_client() -> Client:
    """Return the Supabase client initialised with the **service_role** key.
    Use this for server-side DB operations that need to bypass RLS."""
    global _supabase_admin_client
    if _supabase_admin_client is None:
        key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
        if not SUPABASE_URL or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
            )
        _supabase_admin_client = create_client(SUPABASE_URL, key)
    return _supabase_admin_client
