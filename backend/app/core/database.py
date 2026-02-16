import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

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
async def get_tenant_session(tenant_id: uuid.UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Scoped session with RLS tenant context.

    MUST be used for all DB access. Sets app.tenant_id on checkout,
    resets on return to prevent cross-tenant leakage.
    """
    async with async_session_factory() as session:
        # SET doesn't support parameterized queries in asyncpg;
        # tenant_id is a validated UUID so string interpolation is safe
        tid_str = str(tenant_id)
        await session.execute(
            text(f"SET app.tenant_id = '{tid_str}'")
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.execute(text("RESET app.tenant_id"))
