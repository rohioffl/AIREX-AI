"""Database engine and tenant-scoped async session helpers."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
import structlog

from airex_core.core.config import settings


logger = structlog.get_logger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_tenant_session(
    tenant_id: uuid.UUID,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transaction-scoped async session configured with tenant RLS context."""
    async with async_session_factory() as session:
        tid_str = str(tenant_id)
        context_vars: dict[str, Any] = structlog.contextvars.get_contextvars()
        correlation_id = context_vars.get("correlation_id")
        bound_logger = logger.bind(correlation_id=correlation_id, tenant_id=tid_str)

        try:
            # SET doesn't support parameterized queries in asyncpg;
            # tenant_id is a validated UUID so string interpolation is safe.
            await session.execute(text(f"SET app.tenant_id = '{tid_str}'"))
        except SQLAlchemyError:
            bound_logger.exception("database.tenant_context_set_failed")
            raise

        try:
            yield session
            await session.commit()
        except SQLAlchemyError:
            bound_logger.exception("database.transaction_failed")
            await session.rollback()
            raise
        except Exception:
            bound_logger.exception("database.unexpected_error")
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("RESET app.tenant_id"))
            except SQLAlchemyError:
                bound_logger.exception("database.tenant_context_reset_failed")
                raise
