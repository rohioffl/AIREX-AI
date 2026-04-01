from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class EvidenceContract(BaseModel):
    """Structured investigation evidence payload."""

    summary: str
    signals: list[str] = Field(default_factory=list)
    root_cause: str
    affected_entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    raw_refs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("summary", "root_cause", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("signals", mode="before")
    @classmethod
    def _normalize_signals(cls, value: object) -> object:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("affected_entities", mode="before")
    @classmethod
    def _normalize_entities(cls, value: object) -> object:
        if not isinstance(value, list):
            return value

        normalized: list[str] = []
        for item in value:
            entity = str(item).strip()
            if not entity:
                continue
            if ":" not in entity:
                entity = f"service:{entity.lower()}"
            else:
                entity_type, entity_name = entity.split(":", 1)
                entity = f"{entity_type.strip().lower()}:{entity_name.strip().lower()}"
            normalized.append(entity)
        return normalized


__all__ = ["EvidenceContract"]
