"""Separate SQLAlchemy engine and session factory for the platform_admins table.

Pointed at PLATFORM_ADMIN_DATABASE_URL if set; falls back to the main DATABASE_URL.
This ensures that even if a separate physical database is never configured, the
code always uses a distinct connection pool — keeping platform admin queries
fully isolated from tenant RLS sessions.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airex_core.core.config import settings


def _get_platform_admin_url() -> str:
    return settings.PLATFORM_ADMIN_DATABASE_URL or settings.DATABASE_URL


_platform_admin_engine = create_async_engine(
    _get_platform_admin_url(),
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)

platform_admin_session_factory = async_sessionmaker(
    _platform_admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_platform_admin_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an isolated AsyncSession for platform admin ops."""
    async with platform_admin_session_factory() as session:
        async with session.begin():
            yield session
