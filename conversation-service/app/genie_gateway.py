"""Client for the genie-service.

genie-service now exposes a single `process-message` operation that does the whole
Genie flow (start/follow-up -> poll -> fetch result) and returns a normalized answer,
so this gateway is a thin forwarder.
"""
from __future__ import annotations

from typing import Optional

import httpx

from .config import get_settings


class GatewayError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"genie-service error {status_code}: {detail}")


class GenieGateway:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base = self.settings.genie_service_url

    async def process_message(
        self, question: str, conversation_id: Optional[str] = None
    ) -> dict:
        payload: dict = {"content": question}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        url = f"{self.base}/genie/process-message"
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise GatewayError(502, f"Could not reach genie-service: {exc}") from exc
        if resp.status_code >= 400:
            raise GatewayError(resp.status_code, resp.text)
        return resp.json() if resp.content else {}
