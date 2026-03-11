"""Comment model for incident collaboration."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airex_core.models.base import Base, TenantMixin


class Comment(Base, TenantMixin):
    """Comment on an incident for collaboration."""

    __tablename__ = "comments"
    __table_args__ = (
        {"comment": "Comments on incidents for collaboration"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), default=uuid.uuid4, primary_key=True
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys="[Comment.tenant_id, Comment.user_id]",
        primaryjoin=(
            "and_(Comment.tenant_id == User.tenant_id, "
            "Comment.user_id == User.id)"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Comment(tenant_id={self.tenant_id!s}, "
            f"incident_id={self.incident_id!s}, "
            f"user_id={self.user_id!s}, "
            f"created_at={self.created_at!s})"
        )
