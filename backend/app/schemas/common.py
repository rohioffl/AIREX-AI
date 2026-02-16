import uuid

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class MessageResponse(BaseModel):
    message: str
    incident_id: uuid.UUID | None = None
