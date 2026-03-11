"""Common response schemas shared across backend endpoints."""

import uuid

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    """Basic service health payload used by lightweight health endpoints."""

    status: str
    service: str

    @field_validator("status", "service", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        """Trim surrounding whitespace for human-readable text fields."""
        if isinstance(value, str):
            return value.strip()
        return value


class MessageResponse(BaseModel):
    """Generic message response with optional incident reference."""

    message: str
    incident_id: uuid.UUID | None = Field(default=None)

    @field_validator("message", mode="before")
    @classmethod
    def normalize_message(cls, value: object) -> object:
        """Trim message text to keep API responses consistent."""
        if isinstance(value, str):
            return value.strip()
        return value
