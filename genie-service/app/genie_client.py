"""Thin async client for the Databricks Genie REST API.

Docs: https://docs.databricks.com/api/workspace/genie
"""
from __future__ import annotations

import asyncio

import httpx

from .config import get_settings
from . import parsing


class GenieError(Exception):
    """Raised when the Databricks Genie API returns an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Genie API error {status_code}: {detail}")


class GenieClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _space_base(self) -> str:
        return (
            f"{self.settings.databricks_host}"
            f"/api/2.0/genie/spaces/{self.settings.genie_space_id}"
        )

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        # Databricks Genie rate-limits (429); back off and retry a few times.
        max_retries = 4
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(
                timeout=self.settings.request_timeout
            ) as client:
                try:
                    resp = await client.request(
                        method, url, headers=self.settings.auth_header, **kwargs
                    )
                except httpx.RequestError as exc:
                    raise GenieError(502, f"Could not reach Databricks: {exc}") from exc

            if resp.status_code == 429 and attempt < max_retries:
                # Honor Retry-After if present, else exponential-ish backoff.
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                await asyncio.sleep(delay)
                continue

            if resp.status_code >= 400:
                raise GenieError(resp.status_code, resp.text)

            return resp.json() if resp.content else {}

        raise GenieError(
            429, "Databricks is rate-limiting requests. Please try again shortly."
        )

    # --- Genie operations -------------------------------------------------

    async def start_conversation(self, content: str) -> dict:
        """POST /genie/spaces/{space_id}/start-conversation"""
        url = f"{self._space_base()}/start-conversation"
        return await self._request("POST", url, json={"content": content})

    async def create_message(self, conversation_id: str, content: str) -> dict:
        """POST /genie/spaces/{space_id}/conversations/{conversation_id}/messages"""
        url = f"{self._space_base()}/conversations/{conversation_id}/messages"
        return await self._request("POST", url, json={"content": content})

    async def get_message(self, conversation_id: str, message_id: str) -> dict:
        """GET .../conversations/{conversation_id}/messages/{message_id}"""
        url = (
            f"{self._space_base()}/conversations/{conversation_id}"
            f"/messages/{message_id}"
        )
        return await self._request("GET", url)

    async def get_query_result(self, conversation_id: str, message_id: str) -> dict:
        """GET .../messages/{message_id}/query-result"""
        url = (
            f"{self._space_base()}/conversations/{conversation_id}"
            f"/messages/{message_id}/query-result"
        )
        return await self._request("GET", url)

    # --- High-level, single-operation flow --------------------------------

    async def process_message(
        self, content: str, conversation_id: str | None = None
    ) -> dict:
        """Submit a question and return the fully-resolved answer.

        Does everything in one call:
          1. Start a new conversation, or send a follow-up if conversation_id given.
          2. Poll the message until it reaches a terminal status.
          3. If it completed with a SQL query, fetch and parse the result table.

        Returns a normalized dict:
          {conversation_id, message_id, status, done, answer_text, sql, result, error}
        """
        if conversation_id:
            raw = await self.create_message(conversation_id, content)
            message_id = raw.get("message_id") or raw.get("id")
        else:
            raw = await self.start_conversation(content)
            conversation_id, message_id = parsing.extract_ids(raw)

        if not conversation_id or not message_id:
            raise GenieError(502, f"Unexpected submit response: {raw}")

        message = await self._poll_until_terminal(conversation_id, message_id)
        status = parsing.message_status(message)

        response = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "status": status,
            "done": True,
            "answer_text": parsing.extract_answer_text(message),
            "sql": parsing.extract_sql(message),
            "result": None,
            "error": None,
        }

        if status == "FAILED":
            response["error"] = (
                parsing.extract_error(message) or "Genie failed to answer the question."
            )
            return response

        if status == "COMPLETED" and parsing.has_query_attachment(message):
            try:
                raw_result = await self.get_query_result(conversation_id, message_id)
                response["result"] = parsing.parse_query_result(raw_result)
            except GenieError as exc:
                response["error"] = f"Could not fetch query result: {exc.detail}"

        return response

    async def _poll_until_terminal(
        self, conversation_id: str, message_id: str
    ) -> dict:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.settings.poll_timeout
        while True:
            message = await self.get_message(conversation_id, message_id)
            if parsing.message_status(message) in parsing.TERMINAL_STATUSES:
                return message
            if loop.time() >= deadline:
                raise GenieError(
                    504,
                    f"Timed out after {self.settings.poll_timeout}s waiting for Genie.",
                )
            await asyncio.sleep(self.settings.poll_interval)
