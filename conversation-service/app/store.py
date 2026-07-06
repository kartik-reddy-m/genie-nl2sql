"""Redis-backed conversation history, partitioned per user.

Layout:
  conv:{id}            -> JSON {id, owner, title, created_at, updated_at, messages: [...]}
  conv:index:{owner}   -> sorted set (score = updated_at epoch, member = conversation id)
                          one index per user (owner = authenticated email) so each user
                          only ever sees their own conversations.

`owner` is the authenticated user's email (or "anonymous" when auth is disabled).

Each turn stores two messages in the UI's own shape so a thread can be reloaded
and rendered directly:
  {"role": "user", "text": <question>}
  {"role": "assistant", "status", "text": <answer>, "sql", "result", "error"}
"""
from __future__ import annotations

import json
import time
from typing import Optional

import redis.asyncio as redis

from .config import get_settings

CONV_KEY = "conv:{id}"


def _index_key(owner: str) -> str:
    return f"conv:index:{owner}"


class ConversationStore:
    def __init__(self) -> None:
        self._redis = redis.from_url(
            get_settings().redis_url, decode_responses=True
        )

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    async def add_turn(
        self,
        conversation_id: str,
        user_text: str,
        assistant: dict,
        owner: str,
        title_hint: Optional[str] = None,
    ) -> None:
        key = CONV_KEY.format(id=conversation_id)
        now = time.time()

        raw = await self._redis.get(key)
        if raw:
            conv = json.loads(raw)
        else:
            conv = {
                "id": conversation_id,
                "owner": owner,
                "title": (title_hint or user_text or "Untitled").strip()[:80],
                "created_at": now,
                "messages": [],
            }

        # Preserve the original owner; index under whoever owns it.
        owner = conv.get("owner", owner)

        conv["messages"].append({"role": "user", "text": user_text})
        conv["messages"].append(
            {
                "role": "assistant",
                "status": assistant.get("status"),
                "text": assistant.get("answer_text"),
                "sql": assistant.get("sql"),
                "result": assistant.get("result"),
                "error": assistant.get("error"),
            }
        )
        conv["updated_at"] = now

        await self._redis.set(key, json.dumps(conv))
        await self._redis.zadd(_index_key(owner), {conversation_id: now})

    async def list_conversations(self, owner: str) -> list[dict]:
        ids = await self._redis.zrevrange(_index_key(owner), 0, -1)
        if not ids:
            return []
        raws = await self._redis.mget([CONV_KEY.format(id=i) for i in ids])
        out: list[dict] = []
        for raw in raws:
            if not raw:
                continue
            conv = json.loads(raw)
            out.append(
                {
                    "id": conv["id"],
                    "title": conv.get("title"),
                    "updated_at": conv.get("updated_at"),
                    "message_count": len(conv.get("messages", [])),
                }
            )
        return out

    async def get_conversation(
        self, conversation_id: str, owner: str
    ) -> Optional[dict]:
        raw = await self._redis.get(CONV_KEY.format(id=conversation_id))
        if not raw:
            return None
        conv = json.loads(raw)
        if conv.get("owner") != owner:
            return None  # not this user's conversation
        return conv

    async def owner_of(self, conversation_id: str) -> Optional[str]:
        raw = await self._redis.get(CONV_KEY.format(id=conversation_id))
        if not raw:
            return None
        return json.loads(raw).get("owner")

    async def delete_conversation(self, conversation_id: str, owner: str) -> bool:
        conv = await self.get_conversation(conversation_id, owner)
        if not conv:
            return False
        await self._redis.delete(CONV_KEY.format(id=conversation_id))
        await self._redis.zrem(_index_key(owner), conversation_id)
        return True
