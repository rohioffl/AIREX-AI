import uuid
from datetime import datetime, timezone

from sqlalchemy import PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentLock(Base):
    """
    DB-level lock record for observability.

    The primary distributed lock is Redis. This table is write-only audit
    so operators can inspect lock history.
    """

    __tablename__ = "incident_locks"
    __table_args__ = (PrimaryKeyConstraint("tenant_id", "incident_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return (
            "IncidentLock("
            f"tenant_id={self.tenant_id!s}, "
            f"incident_id={self.incident_id!s}, "
            f"worker_id={self.worker_id!r}"
            ")"
        )
