"""Feedback learning model for tracking approval/rejection patterns."""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, ForeignKeyConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base, TenantMixin


class FeedbackLearning(Base, TenantMixin):
    """Tracks user feedback on AI recommendations for learning."""

    __tablename__ = "feedback_learning"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    recommendation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_taken: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'approved', 'rejected', 'modified'
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    confidence_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # Foreign key
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "incident_id"],
            ["incidents.tenant_id", "incidents.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"FeedbackLearning(tenant_id={self.tenant_id!s}, "
            f"id={self.id!s}, incident_id={self.incident_id!s}, "
            f"action_taken={self.action_taken!r})"
        )
