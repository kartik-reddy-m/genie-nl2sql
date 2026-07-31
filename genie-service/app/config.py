import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime configuration loaded from environment / .env."""

    def __init__(self) -> None:
        self.databricks_host: str = os.getenv("DATABRICKS_HOST", "").rstrip("/")
        self.databricks_token: str = os.getenv("DATABRICKS_TOKEN", "")
        self.genie_space_id: str = os.getenv("GENIE_SPACE_ID", "")
        self.request_timeout: float = float(os.getenv("GENIE_REQUEST_TIMEOUT", "60"))
        # Server-side polling budget for a single process-message operation.
        self.poll_interval: float = float(os.getenv("GENIE_POLL_INTERVAL", "2.5"))
        self.poll_timeout: float = float(os.getenv("GENIE_POLL_TIMEOUT", "150"))
        # Shared secret; when set, callers must send it as X-Internal-Key.
        # Blank => guard disabled (local dev).
        self.internal_api_key: str = os.getenv("INTERNAL_API_KEY", "").strip()

    @property
    def auth_header(self) -> dict:
        return {"Authorization": f"Bearer {self.databricks_token}"}

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("DATABRICKS_HOST", self.databricks_host),
                ("DATABRICKS_TOKEN", self.databricks_token),
                ("GENIE_SPACE_ID", self.genie_space_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env and fill it in."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
