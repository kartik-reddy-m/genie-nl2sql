"""Google OAuth token verification for the conversation-service API.

The SPA signs in with Google Identity Services and sends the resulting ID token
as `Authorization: Bearer <token>`. Here we verify that token against our Google
client id and (optionally) restrict access to an email/domain allowlist.

If GOOGLE_CLIENT_ID is not configured, auth is disabled (handy for local dev).
"""
from __future__ import annotations

from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .config import get_settings

_request = google_requests.Request()


def _is_allowed(email: str) -> bool:
    settings = get_settings()
    email = (email or "").lower()
    if settings.allowed_emails:
        if email in settings.allowed_emails:
            return True
    if settings.allowed_email_domains:
        domain = email.split("@")[-1] if "@" in email else ""
        if domain in settings.allowed_email_domains:
            return True
    # No allowlist configured -> any verified Google account is accepted.
    return not settings.allowed_emails and not settings.allowed_email_domains


async def require_user(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency: returns the authenticated user, or raises 401/403."""
    settings = get_settings()

    if not settings.auth_enabled:
        return {"email": "anonymous", "auth": "disabled"}

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        info = google_id_token.verify_oauth2_token(
            token, _request, settings.google_client_id
        )
    except Exception as exc:  # noqa: BLE001 - any verification failure => 401
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    if not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Email not verified")

    email = info.get("email", "")
    if not _is_allowed(email):
        raise HTTPException(status_code=403, detail="Not authorized for this app")

    return {"email": email, "name": info.get("name"), "picture": info.get("picture")}
