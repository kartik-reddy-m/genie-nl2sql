from typing import Optional

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Ask a question. Omit conversation_id to start a new conversation;
    pass it to send a follow-up in an existing conversation."""

    content: str = Field(..., min_length=1, description="Natural-language question.")
    conversation_id: Optional[str] = Field(
        default=None, description="Existing conversation id for a follow-up."
    )
