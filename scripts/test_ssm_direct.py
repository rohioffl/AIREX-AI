#!/usr/bin/env python3
# ruff: noqa: E402
"""
Test SSM directly with instance ID (bypasses discovery).

Usage:
    python -m scripts.test_ssm_direct i-1234567890abcdef0 [--region ap-south-1]

Or test with IP (will try to discover first):
    python -m scripts.test_ssm_direct --ip 9.9.0.38 [--region ap-south-1]
"""

import argparse
import asyncio
import sys

from airex_core.cloud.aws_ssm import ssm_check_instance_managed, ssm_run_command
from airex_core.cloud.discovery import discover_aws_instance
from airex_core.core.config import settings


async def test_ssm_direct(instance_id: str = "", ip: str = "", region: str = ""):
    """Test SSM connectivity directly."""
    effective_region = region or settings.AWS_REGION

    # If IP provided, discover instance first
    if ip and not instance_id:
        print(f"\n🔍 Discovering instance by IP: {ip}")
        discovered = await discover_aws_instance(
            private_ip=ip,
            region=effective_region,
        )
        if not discovered:
            print(f"❌ Could not discover instance with IP {ip}")
            print("\n💡 To test SSM directly, you can:")
            print("   1. Configure AWS credentials (see services/airex-core/config/tenants.yaml)")
            print(
                "   2. Or provide instance ID directly: python -m scripts.test_ssm_direct i-xxxxx"
            )
            return False
        instance_id = discovered.instance_id
        effective_region = discovered.region
        print(f"✅ Found instance: {instance_id} in {effective_region}")

    if not instance_id:
        print("❌ Need either instance_id or ip")
        return False

    print(f"\n🔍 Testing SSM for Instance: {instance_id}")
    print(f"   Region: {effective_region}")
    print("=" * 60)

    # Check if managed
    print("\n[1/3] Checking if instance is managed by SSM...")
    is_managed = await ssm_check_instance_managed(
        instance_id=instance_id,
        region=effective_region,
    )

    if not is_managed:
        print("❌ Instance is NOT managed by SSM")
        print("\n📋 Requirements for SSM:")
        print("   1. SSM Agent must be installed and running")
        print(
            "   2. Instance must have IAM role with 'AmazonSSMManagedInstanceCore' policy"
        )
        print("   3. SSM Agent must be connected to SSM service (check PingStatus)")
        print("\n💡 Troubleshooting:")
        print("   - Check SSM Agent: sudo systemctl status amazon-ssm-agent")
        print(
            "   - Check IAM role: aws ec2 describe-instances --instance-ids {instance_id}"
        )
        print(
            "   - Check SSM status: aws ssm describe-instance-information --filters Key=InstanceIds,Values={instance_id}"
        )
        return False

    print("✅ Instance IS managed by SSM")

    # Test simple command
    print("\n[2/3] Testing simple SSM command...")
    try:
        output = await ssm_run_command(
            instance_id=instance_id,
            commands=["echo 'SSM Test Success - $(date)'", "hostname", "whoami"],
            region=effective_region,
        )
        print("✅ SSM command executed successfully!")
        print("\n📋 Output:")
        print("-" * 60)
        print(output)
        print("-" * 60)
    except Exception as exc:
        print(f"❌ SSM command failed: {exc}")
        return False

    # Test diagnostic command
    print("\n[3/3] Testing diagnostic command...")
    try:
        output = await ssm_run_command(
            instance_id=instance_id,
            commands=[
                "uptime",
                "df -h | head -5",
                "free -h",
                "ps aux | head -5",
            ],
            region=effective_region,
        )
        print("✅ Diagnostic command executed successfully!")
        print("\n📋 Diagnostic Output:")
        print("-" * 60)
        print(output)
        print("-" * 60)
    except Exception as exc:
        print(f"⚠️  Diagnostic command failed: {exc}")
        print("   (SSM is working, but diagnostic command had issues)")

    print("\n✅ SSM Test Complete!")
    print("\n💡 This instance can be used for AIREX investigations")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test SSM connectivity")
    parser.add_argument(
        "instance_id", nargs="?", help="EC2 instance ID (e.g. i-1234567890abcdef0)"
    )
    parser.add_argument("--ip", help="Private IP address (will discover instance)")
    parser.add_argument("--region", default="", help="AWS region")

    args = parser.parse_args()

    if not args.instance_id and not args.ip:
        parser.print_help()
        sys.exit(1)

    success = asyncio.run(
        test_ssm_direct(
            instance_id=args.instance_id or "",
            ip=args.ip or "",
            region=args.region,
        )
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
