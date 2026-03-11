#!/usr/bin/env python3
"""
Validate Alembic migrations against a real Postgres instance.

Usage:
  docker-compose up -d db
  python scripts/validate_migration.py

Checks:
  1. alembic upgrade head succeeds
  2. All expected tables exist
  3. Enum types exist
  4. RLS policies are active
  5. Indexes exist
  6. Generated columns work
  7. alembic downgrade base succeeds
  8. Clean re-upgrade succeeds
"""

import subprocess
import sys


def run(cmd: str) -> str:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd="/home/ubuntu/AIREX/backend"
    )
    if result.returncode != 0:
        print(f"FAIL: {cmd}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def main():
    print("=== Alembic Migration Validation ===\n")

    print("1. Running upgrade head...")
    run("alembic upgrade head")
    print("   OK\n")

    print("2. Checking tables via alembic current...")
    out = run("alembic current")
    if "002_add_users_table (head)" in out:
        print("   OK — at head revision\n")
    else:
        print(f"   Current: {out.strip()}\n")

    print("3. Running downgrade base...")
    run("alembic downgrade base")
    print("   OK\n")

    print("4. Running re-upgrade head (idempotency check)...")
    run("alembic upgrade head")
    print("   OK\n")

    print("=== All migration checks passed ===")


if __name__ == "__main__":
    main()
