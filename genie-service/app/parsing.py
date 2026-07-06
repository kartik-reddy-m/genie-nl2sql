"""Helpers to normalize Databricks Genie responses into a clean shape."""
from __future__ import annotations

from typing import Any, Optional

# Genie message lifecycle statuses that mean "no more work is happening".
TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "QUERY_RESULT_EXPIRED",
}


def extract_ids(start_response: dict) -> tuple[str, str]:
    """Pull conversation_id and message_id out of a start-conversation response.

    Handles both the flat form (conversation_id/message_id) and the nested form
    (conversation.id / message.id).
    """
    conversation_id = start_response.get("conversation_id") or (
        start_response.get("conversation") or {}
    ).get("id")
    message_id = start_response.get("message_id") or (
        start_response.get("message") or {}
    ).get("id")
    return conversation_id, message_id


def message_status(message: dict) -> str:
    return message.get("status") or "UNKNOWN"


def extract_answer_text(message: dict) -> Optional[str]:
    """A Genie message may carry a plain-text answer in an attachment."""
    for att in message.get("attachments") or []:
        text = att.get("text")
        if text and text.get("content"):
            return text["content"]
    return message.get("content")


def extract_sql(message: dict) -> Optional[str]:
    for att in message.get("attachments") or []:
        query = att.get("query")
        if query and query.get("query"):
            return query["query"]
    return None


def has_query_attachment(message: dict) -> bool:
    return any((att.get("query") for att in message.get("attachments") or []))


def extract_error(message: dict) -> Optional[str]:
    err = message.get("error")
    if isinstance(err, dict):
        return err.get("message")
    return err


def _row_from_typed(entry: dict) -> list[Any]:
    """A data_typed_array row is {"values": [{"str": "..."}, ...]}.

    Each cell is a typed object; a SQL NULL comes back as an empty/None cell.
    """
    cells = entry.get("values") or []
    row: list[Any] = []
    for cell in cells:
        if not isinstance(cell, dict) or not cell:
            row.append(None)
        else:
            row.append(
                cell.get("str") if "str" in cell else next(iter(cell.values()), None)
            )
    return row


def parse_query_result(raw: dict) -> Optional[dict]:
    """Turn a Genie query-result payload into {columns, rows, row_count}.

    Genie returns a `statement_response` with a `manifest.schema.columns` list
    and a `result` that carries rows either as:
      - `data_typed_array`: [{"values": [{"str": "v"}, ...]}, ...]  (typed), or
      - `data_array`:       [["v", ...], ...]                       (plain).
    """
    statement = raw.get("statement_response") or raw
    manifest = statement.get("manifest") or {}
    schema = manifest.get("schema") or {}
    columns = [
        col.get("name", f"col_{i}")
        for i, col in enumerate(schema.get("columns") or [])
    ]

    result = statement.get("result") or {}
    if result.get("data_typed_array") is not None:
        rows = [_row_from_typed(entry) for entry in result["data_typed_array"]]
    else:
        rows = result.get("data_array") or []

    if not columns and not rows:
        return None

    return {"columns": columns, "rows": rows, "row_count": len(rows)}
