#!/usr/bin/env python3
# ruff: noqa: E402
"""
Manage platform admin accounts in the platform_admins table.

The platform_admins table is isolated from tenant users — no tenant_id,
no RLS. Use this script to add, list, activate, or deactivate admins.

Usage:
    # Add a new platform admin (prompts for password if omitted)
    python -m scripts.manage_platform_admins add --email admin@example.com --name "Alice"

    # Add with password inline
    python -m scripts.manage_platform_admins add --email admin@example.com --password "S3cur3!" --name "Alice"

    # List all platform admins
    python -m scripts.manage_platform_admins list

    # Deactivate an admin
    python -m scripts.manage_platform_admins deactivate --email admin@example.com

    # Reactivate an admin
    python -m scripts.manage_platform_admins activate --email admin@example.com

    # Update password
    python -m scripts.manage_platform_admins set-password --email admin@example.com

Environment:
    DATABASE_URL or PLATFORM_ADMIN_DATABASE_URL must be set (reads from .env automatically
    via airex_core settings).
"""

import argparse
import asyncio
import getpass
import sys
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from airex_core.core.config import settings
from airex_core.core.security import hash_password


def _get_db_url() -> str:
    pa_url = getattr(settings, "PLATFORM_ADMIN_DATABASE_URL", "") or ""
    return pa_url if pa_url.strip() else settings.DATABASE_URL


async def _get_session() -> tuple:
    engine = create_async_engine(_get_db_url(), echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_add(email: str, password: str, display_name: str) -> None:
    engine, factory = await _get_session()
    async with factory() as session:
        existing = (
            await session.execute(text("SELECT id FROM platform_admins WHERE email = :e"), {"e": email})
        ).fetchone()
        if existing:
            print(f"❌  Platform admin '{email}' already exists (id={existing[0]}). Use set-password to update.")
            await engine.dispose()
            sys.exit(1)

        new_id = uuid.uuid4()
        hashed = hash_password(password)
        await session.execute(
            text("""
                INSERT INTO platform_admins (id, email, hashed_password, display_name, is_active)
                VALUES (:id, :email, :pw, :name, TRUE)
            """),
            {"id": str(new_id), "email": email, "pw": hashed, "name": display_name},
        )
        await session.commit()

    await engine.dispose()
    print("✅  Platform admin created!")
    print(f"    ID:    {new_id}")
    print(f"    Email: {email}")
    print(f"    Name:  {display_name}")


async def cmd_list() -> None:
    engine, factory = await _get_session()
    async with factory() as session:
        rows = (
            await session.execute(
                text("SELECT id, email, display_name, is_active, created_at FROM platform_admins ORDER BY created_at")
            )
        ).fetchall()

    await engine.dispose()

    if not rows:
        print("No platform admins found.")
        return

    print(f"{'ID':<38}  {'Email':<35}  {'Name':<25}  Active  Created")
    print("-" * 120)
    for row in rows:
        active = "✓" if row[3] else "✗"
        print(f"{str(row[0]):<38}  {row[1]:<35}  {row[2]:<25}  {active:<6}  {row[4]}")


async def cmd_set_active(email: str, active: bool) -> None:
    engine, factory = await _get_session()
    async with factory() as session:
        result = await session.execute(
            text("UPDATE platform_admins SET is_active = :a, updated_at = NOW() WHERE email = :e RETURNING id"),
            {"a": active, "e": email},
        )
        row = result.fetchone()
        await session.commit()

    await engine.dispose()

    if not row:
        print(f"❌  Platform admin '{email}' not found.")
        sys.exit(1)

    status = "activated" if active else "deactivated"
    print(f"✅  Platform admin '{email}' {status}.")


async def cmd_set_password(email: str, password: str) -> None:
    engine, factory = await _get_session()
    async with factory() as session:
        hashed = hash_password(password)
        result = await session.execute(
            text("UPDATE platform_admins SET hashed_password = :pw, updated_at = NOW() WHERE email = :e RETURNING id"),
            {"pw": hashed, "e": email},
        )
        row = result.fetchone()
        await session.commit()

    await engine.dispose()

    if not row:
        print(f"❌  Platform admin '{email}' not found.")
        sys.exit(1)

    print(f"✅  Password updated for '{email}'.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _prompt_password(confirm: bool = True) -> str:
    pw = getpass.getpass("Password: ")
    if confirm:
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print("❌  Passwords do not match.")
            sys.exit(1)
    if len(pw) < 8:
        print("❌  Password must be at least 8 characters.")
        sys.exit(1)
    return pw


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage AIREX platform admin accounts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a new platform admin")
    p_add.add_argument("--email", required=True, help="Admin email address")
    p_add.add_argument("--password", default=None, help="Password (prompted if omitted)")
    p_add.add_argument("--name", default="Platform Admin", help="Display name")

    # list
    sub.add_parser("list", help="List all platform admins")

    # deactivate
    p_deact = sub.add_parser("deactivate", help="Deactivate a platform admin")
    p_deact.add_argument("--email", required=True)

    # activate
    p_act = sub.add_parser("activate", help="Re-activate a platform admin")
    p_act.add_argument("--email", required=True)

    # set-password
    p_pw = sub.add_parser("set-password", help="Update a platform admin's password")
    p_pw.add_argument("--email", required=True)
    p_pw.add_argument("--password", default=None, help="New password (prompted if omitted)")

    args = parser.parse_args()

    if args.command == "add":
        password = args.password or _prompt_password(confirm=True)
        asyncio.run(cmd_add(args.email, password, args.name))

    elif args.command == "list":
        asyncio.run(cmd_list())

    elif args.command == "deactivate":
        asyncio.run(cmd_set_active(args.email, active=False))

    elif args.command == "activate":
        asyncio.run(cmd_set_active(args.email, active=True))

    elif args.command == "set-password":
        password = args.password or _prompt_password(confirm=True)
        asyncio.run(cmd_set_password(args.email, password))


if __name__ == "__main__":
    main()
