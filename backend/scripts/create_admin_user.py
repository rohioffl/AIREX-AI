#!/usr/bin/env python3
# ruff: noqa: E402
"""
Create an admin user in the database.

Usage:
    python -m scripts.create_admin_user [--email admin@example.com] [--password admin123] [--name "Admin User"] [--tenant-id <uuid>]
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User


async def create_admin_user(
    email: str,
    password: str,
    display_name: str,
    tenant_id: uuid.UUID | None = None,
):
    """Create an admin user in the database."""
    # Use default tenant ID if not provided
    if tenant_id is None:
        tenant_id = (
            uuid.UUID(settings.DEV_TENANT_ID)
            if hasattr(settings, "DEV_TENANT_ID")
            else uuid.UUID("00000000-0000-0000-0000-000000000000")
        )

    # Create database engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"❌ User with email '{email}' already exists!")
            print(f"   User ID: {existing.id}")
            print(f"   Role: {existing.role}")
            return False

        # Create new admin user
        user = User(
            tenant_id=tenant_id,
            email=email,
            hashed_password=hash_password(password),
            display_name=display_name,
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()

        print("✅ Admin user created successfully!")
        print(f"   Email: {user.email}")
        print(f"   Display Name: {user.display_name}")
        print(f"   Role: {user.role}")
        print(f"   User ID: {user.id}")
        print(f"   Tenant ID: {user.tenant_id}")
        return True

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument(
        "--email", default="admin@example.com", help="Admin email address"
    )
    parser.add_argument("--password", default="admin123", help="Admin password")
    parser.add_argument("--name", default="Admin User", help="Display name")
    parser.add_argument("--tenant-id", type=str, help="Tenant ID (UUID)")

    args = parser.parse_args()

    tenant_id = None
    if args.tenant_id:
        try:
            tenant_id = uuid.UUID(args.tenant_id)
        except ValueError:
            print(f"❌ Invalid tenant ID: {args.tenant_id}")
            sys.exit(1)

    print("Creating admin user...")
    print(f"  Email: {args.email}")
    print(f"  Display Name: {args.name}")
    print(f"  Tenant ID: {tenant_id or 'default'}")
    print()

    success = asyncio.run(
        create_admin_user(
            email=args.email,
            password=args.password,
            display_name=args.name,
            tenant_id=tenant_id,
        )
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
