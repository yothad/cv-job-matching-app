"""Single place that turns an Authorization header into a Supabase user id.

supabase.auth.get_user() RAISES on an invalid/expired token instead of returning
an empty user. Unhandled, that became a 500 with no CORS headers, which the
browser reports as an opaque "Failed to fetch". Every router calls require_user
so a bad token is always a clean 401 JSON response.
"""
from fastapi import HTTPException

from db.supabase_client import supabase


def require_user(authorization: str | None) -> str:
    """Return the signed-in user's id, or raise HTTPException(401)."""
    return require_user_and_email(authorization)[0]


def require_user_and_email(authorization: str | None) -> tuple[str, str | None]:
    """Same check as require_user, plus the verified user's email (None if absent)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not signed in")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        resp = supabase.auth.get_user(token)
    except Exception:
        # Never echo the token or the upstream error text.
        raise HTTPException(status_code=401, detail="Session expired - please sign in again")
    user = getattr(resp, "user", None)
    if not user or not getattr(user, "id", None):
        raise HTTPException(status_code=401, detail="Session expired - please sign in again")
    return user.id, getattr(user, "email", None)
