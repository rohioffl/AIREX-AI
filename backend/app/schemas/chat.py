"""Pydantic schemas for incident AI chat (Phase 7)."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Operator chat message sent to the AI."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The operator's question or message about the incident",
    )


class ChatMessage(BaseModel):
    """A single message in the conversation history."""

    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'",
    )
    content: str


class ChatResponse(BaseModel):
    """AI response to the operator's chat message."""

    reply: str = Field(..., description="AI assistant response text")
    conversation_length: int = Field(
        ...,
        description="Total messages in conversation history (including this exchange)",
    )
