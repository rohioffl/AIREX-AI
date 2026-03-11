#!/usr/bin/env python3
# ruff: noqa: E402
"""
Test SSM connectivity for a specific IP address.

Usage:
    python -m scripts.test_ssm 9.9.0.38 [--region ap-south-1]
"""

import argparse
import asyncio
import sys

from airex_core.cloud.aws_ssm import ssm_check_instance_managed, ssm_run_command
from airex_core.cloud.discovery import discover_aws_instance
from airex_core.core.config import settings


async def test_ssm_for_ip(private_ip: str, region: str = ""):
    """Test SSM connectivity for an IP address."""
    print(f"\n🔍 Testing SSM for IP: {private_ip}")
    print("=" * 60)

    # Step 1: Discover instance
    print(f"\n[1/4] Discovering instance by IP: {private_ip}")
    discovered = await discover_aws_instance(
        private_ip=private_ip,
        region=region or settings.AWS_REGION,
    )

    if not discovered:
        print(f"❌ Instance not found with IP {private_ip}")
        print("   This could mean:")
        print("   - IP is not in AWS")
        print("   - IP is in a different region")
        print("   - AWS credentials don't have access")
        return False

    print("✅ Instance discovered:")
    print(f"   Instance ID: {discovered.instance_id}")
    print(f"   Name: {discovered.instance_name}")
    print(f"   Region: {discovered.region}")
    print(f"   Zone: {discovered.zone}")
    print(f"   Status: {discovered.status}")
    print(f"   Machine Type: {discovered.machine_type}")

    # Step 2: Check if SSM is managed
    print("\n[2/4] Checking if instance is managed by SSM...")
    is_managed = await ssm_check_instance_managed(
        instance_id=discovered.instance_id,
        region=discovered.region,
    )

    if not is_managed:
        print("❌ Instance is NOT managed by SSM")
        print("   This means:")
        print("   - SSM Agent is not installed/running")
        print("   - Instance doesn't have IAM role with AmazonSSMManagedInstanceCore")
        print("   - SSM Agent is not connected to SSM service")
        return False

    print("✅ Instance IS managed by SSM")

    # Step 3: Test SSM command
    print("\n[3/4] Testing SSM command execution...")
    test_commands = [
        "echo 'SSM Test - $(date)'",
        "hostname",
        "whoami",
        "uptime",
    ]

    try:
        output = await ssm_run_command(
            instance_id=discovered.instance_id,
            commands=test_commands,
            region=discovered.region,
        )
        print("✅ SSM command executed successfully!")
        print("\n📋 Command Output:")
        print("-" * 60)
        print(output)
        print("-" * 60)
    except Exception as exc:
        print(f"❌ SSM command failed: {exc}")
        return False

    # Step 4: Test diagnostic command
    print("\n[4/4] Testing diagnostic command (CPU check)...")
    diagnostic_commands = [
        "top -bn1 | head -5",
        "df -h | head -5",
        "free -h",
    ]

    try:
        output = await ssm_run_command(
            instance_id=discovered.instance_id,
            commands=diagnostic_commands,
            region=discovered.region,
        )
        print("✅ Diagnostic command executed successfully!")
        print("\n📋 Diagnostic Output:")
        print("-" * 60)
        print(output)
        print("-" * 60)
    except Exception as exc:
        print(f"⚠️  Diagnostic command failed: {exc}")
        print("   (This is okay, SSM is still working)")

    print("\n✅ SSM Test Complete - All checks passed!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test SSM connectivity for an IP")
    parser.add_argument("ip", help="Private IP address to test")
    parser.add_argument(
        "--region", default="", help="AWS region (default: auto-discover)"
    )

    args = parser.parse_args()

    success = asyncio.run(test_ssm_for_ip(args.ip, args.region))

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
