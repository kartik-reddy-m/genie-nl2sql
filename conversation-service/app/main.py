"""conversation-service — the API the UI talks to.

Each question is answered in a single request: this service forwards to
genie-service's process-message operation, which starts/continues the Genie
conversation, waits for the answer, and returns the SQL + data. No polling.

Conversations (question + answer turns) are persisted in Redis so the UI can
list past conversations and reload/continue them.
"""
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_user
from .config import get_settings
from .genie_gateway import GatewayError, GenieGateway
from .models import (
    AnswerResponse,
    ConversationDetail,
    ConversationSummary,
    QuestionRequest,
)
from .store import ConversationStore

log = logging.getLogger("conversation-service")

app = FastAPI(title="conversation-service", version="3.0.0")

# Allow the Vite dev server (and others in dev) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

gateway = GenieGateway()
store = ConversationStore()


def _handle(exc: GatewayError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


async def _persist(
    conversation_id: str, question: str, result: dict, owner: str
) -> None:
    """Best-effort save; never let a persistence error break answering."""
    try:
        await store.add_turn(
            conversation_id, question, result, owner=owner, title_hint=question
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to persist conversation %s: %s", conversation_id, exc)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health() -> dict:
    return {
        "status": "ok",
        "service": "conversation-service",
        "redis": await store.ping(),
        "auth_enabled": get_settings().auth_enabled,
    }


@app.post("/conversations", response_model=AnswerResponse)
async def create_conversation(
    body: QuestionRequest, user: dict = Depends(require_user)
) -> AnswerResponse:
    """Start a new conversation and return the fully-resolved answer."""
    try:
        result = await gateway.process_message(body.question)
    except GatewayError as exc:
        raise _handle(exc)
    await _persist(result["conversation_id"], body.question, result, user["email"])
    return AnswerResponse(**result)


@app.post(
    "/conversations/{conversation_id}/messages",
    response_model=AnswerResponse,
)
async def send_message(
    conversation_id: str,
    body: QuestionRequest,
    user: dict = Depends(require_user),
) -> AnswerResponse:
    """Send a follow-up in an existing conversation and return the answer."""
    # Only the owner may continue a conversation.
    existing_owner = await store.owner_of(conversation_id)
    if existing_owner is not None and existing_owner != user["email"]:
        raise HTTPException(403, "Not your conversation")

    try:
        result = await gateway.process_message(body.question, conversation_id)
    except GatewayError as exc:
        raise _handle(exc)
    await _persist(result["conversation_id"], body.question, result, user["email"])
    return AnswerResponse(**result)


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: dict = Depends(require_user),
) -> list[ConversationSummary]:
    """History sidebar: the signed-in user's past conversations, newest first."""
    items = await store.list_conversations(user["email"])
    return [ConversationSummary(**item) for item in items]


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, user: dict = Depends(require_user)
) -> ConversationDetail:
    """Full thread for one of the user's past conversations."""
    conv = await store.get_conversation(conversation_id, user["email"])
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return ConversationDetail(**conv)


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, user: dict = Depends(require_user)
) -> dict:
    deleted = await store.delete_conversation(conversation_id, user["email"])
    if not deleted:
        raise HTTPException(404, "Conversation not found")
    return {"deleted": conversation_id}


@app.get("/me")
async def me(user: dict = Depends(require_user)) -> dict:
    """Who am I — used by the UI to confirm the token is accepted."""
    return user
