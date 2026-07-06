from typing import Any, Optional

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question.")


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int


class AnswerResponse(BaseModel):
    """Fully-resolved answer for a question, returned in a single call."""

    conversation_id: str
    message_id: str
    status: str
    done: bool
    answer_text: Optional[str] = None
    sql: Optional[str] = None
    result: Optional[QueryResult] = None
    error: Optional[str] = None


class ConversationSummary(BaseModel):
    """A row in the history sidebar."""

    id: str
    title: Optional[str] = None
    updated_at: Optional[float] = None
    message_count: int = 0


class StoredMessage(BaseModel):
    role: str
    text: Optional[str] = None
    status: Optional[str] = None
    sql: Optional[str] = None
    result: Optional[QueryResult] = None
    error: Optional[str] = None


class ConversationDetail(BaseModel):
    """Full thread for a past conversation."""

    id: str
    title: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    messages: list[StoredMessage] = []
