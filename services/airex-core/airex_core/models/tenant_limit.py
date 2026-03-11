import uuid

from sqlalchemy import Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from airex_core.models.base import Base


class TenantLimit(Base):
    """
    SaaS rate-limiting configuration per tenant.

    Enforced at the application layer before DB insert.
    """

    __tablename__ = "tenant_limits"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    max_concurrent_incidents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50
    )
    max_daily_executions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200
    )

    def __repr__(self) -> str:
        return (
            "TenantLimit("
            f"tenant_id={self.tenant_id!s}, "
            f"max_concurrent_incidents={self.max_concurrent_incidents}, "
            f"max_daily_executions={self.max_daily_executions}"
            ")"
        )
