import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        genie_url = os.getenv("GENIE_SERVICE_URL", "http://localhost:8001").rstrip("/")
        # Render's fromService gives a bare host with no scheme — public Render
        # services are https. (Local dev always sets an explicit http:// scheme.)
        if not genie_url.startswith(("http://", "https://")):
            genie_url = "https://" + genie_url
        self.genie_service_url: str = genie_url
        # Must exceed genie-service's poll budget (GENIE_POLL_TIMEOUT, default 150s),
        # since a single process-message call blocks until Genie finishes.
        self.request_timeout: float = float(
            os.getenv("CONVERSATION_REQUEST_TIMEOUT", "180")
        )
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        # Shared secret sent to genie-service as X-Internal-Key.
        self.internal_api_key: str = os.getenv("INTERNAL_API_KEY", "").strip()

        # --- Google OAuth ---
        # If google_client_id is empty, auth is DISABLED (local dev convenience).
        self.google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.allowed_emails: set[str] = {
            e.strip().lower()
            for e in os.getenv("GOOGLE_ALLOWED_EMAILS", "").split(",")
            if e.strip()
        }
        self.allowed_email_domains: set[str] = {
            d.strip().lower().lstrip("@")
            for d in os.getenv("GOOGLE_ALLOWED_DOMAINS", "").split(",")
            if d.strip()
        }

    @property
    def auth_enabled(self) -> bool:
        return bool(self.google_client_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
