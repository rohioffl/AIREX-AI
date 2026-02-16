"""
Cloud instance auto-discovery.

Given a private IP and a project/account, discovers the full instance
details (name, zone, region, instance ID) from the GCP or AWS APIs.

Results are cached in Redis (TTL 1 hour) so repeated webhooks for the
same IP don't re-query the cloud API every time.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, asdict
from functools import lru_cache

import structlog

from app.core.config import settings

logger = structlog.get_logger()

DISCOVERY_CACHE_TTL = 3600  # 1 hour


@dataclass
class DiscoveredInstance:
    """Result from cloud instance auto-discovery."""
    cloud: str = ""              # gcp | aws
    instance_name: str = ""      # GCE name or EC2 Name tag
    instance_id: str = ""        # GCE name or EC2 i-xxxx
    private_ip: str = ""
    zone: str = ""               # e.g. asia-south1-a
    region: str = ""             # e.g. ap-south-1
    machine_type: str = ""       # e.g. e2-medium, t3.micro
    status: str = ""             # RUNNING, stopped, etc.
    network: str = ""            # VPC / subnet
    service_account: str = ""    # GCP SA email
    tags: dict = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


# ═══════════════════════════════════════════════════════════════════
#  GCP Discovery
# ═══════════════════════════════════════════════════════════════════

@lru_cache(maxsize=4)
def _get_gcp_compute_client(sa_key_path: str = ""):
    """
    Create a GCP Compute client.

    Auth priority:
      1. Explicit SA key path (per-tenant override in tenants.yaml)
      2. GOOGLE_APPLICATION_CREDENTIALS env var
      3. gcloud auth activate-service-account / application-default login
      4. GCE metadata server (automatic on GCE/GKE/Cloud Run)
    """
    from google.cloud import compute_v1

    if sa_key_path and os.path.exists(sa_key_path):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(sa_key_path)
        logger.info("gcp_auth_explicit_key", key_path=sa_key_path)
        return compute_v1.InstancesClient(credentials=creds)

    # Falls through to ADC: env var → gcloud CLI → GCE metadata
    auth_source = "GOOGLE_APPLICATION_CREDENTIALS" if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") else "ADC/gcloud/metadata"
    logger.info("gcp_auth_adc", source=auth_source)
    return compute_v1.InstancesClient()


async def discover_gcp_instance(
    private_ip: str,
    project_id: str,
    sa_key_path: str = "",
) -> DiscoveredInstance | None:
    """
    Find a GCE instance by its private IP across all zones in the project.

    Uses aggregatedList to search all zones at once — one API call.
    """
    log = logger.bind(private_ip=private_ip, project=project_id)
    log.info("gcp_discovery_starting")

    loop = asyncio.get_event_loop()

    try:
        client = _get_gcp_compute_client(sa_key_path)

        from google.cloud import compute_v1

        request = compute_v1.AggregatedListInstancesRequest(
            project=project_id,
        )

        # aggregatedList returns instances grouped by zone
        result = await loop.run_in_executor(
            None,
            lambda: client.aggregated_list(request=request),
        )

        for zone_scope, instances_scoped in result:
            if not instances_scoped.instances:
                continue
            for inst in instances_scoped.instances:
                # Verify IP match
                for iface in inst.network_interfaces:
                    if iface.network_i_p == private_ip:
                        # Extract zone name from full URL
                        zone_name = inst.zone.split("/")[-1] if inst.zone else ""
                        region = "-".join(zone_name.split("-")[:-1]) if zone_name else ""

                        # Machine type
                        machine_type = inst.machine_type.split("/")[-1] if inst.machine_type else ""

                        # Service account
                        sa_email = ""
                        if inst.service_accounts:
                            sa_email = inst.service_accounts[0].email

                        # Tags/labels
                        labels = dict(inst.labels) if inst.labels else {}

                        discovered = DiscoveredInstance(
                            cloud="gcp",
                            instance_name=inst.name,
                            instance_id=inst.name,
                            private_ip=private_ip,
                            zone=zone_name,
                            region=region,
                            machine_type=machine_type,
                            status=inst.status,
                            network=iface.network.split("/")[-1] if iface.network else "",
                            service_account=sa_email,
                            tags=labels,
                        )

                        log.info(
                            "gcp_instance_discovered",
                            instance=inst.name,
                            zone=zone_name,
                            machine_type=machine_type,
                            status=inst.status,
                        )
                        return discovered

        log.warning("gcp_instance_not_found", private_ip=private_ip)
        return None

    except Exception as exc:
        log.error("gcp_discovery_failed", error=str(exc))
        return None


# ═══════════════════════════════════════════════════════════════════
#  AWS Discovery
# ═══════════════════════════════════════════════════════════════════

async def discover_aws_instance(
    private_ip: str,
    region: str = "",
    aws_config: "AWSConfig | None" = None,
    profile: str = "",
) -> DiscoveredInstance | None:
    """
    Find an EC2 instance by its private IP.

    Uses per-tenant AWSConfig for auth (role assumption, static keys, etc.).
    If region is not specified, auto-searches all available AWS regions.
    """
    log = logger.bind(private_ip=private_ip)
    log.info("aws_discovery_starting")

    loop = asyncio.get_event_loop()

    # Use explicit region only if caller or tenant config provides one
    explicit_region = region or (aws_config.region if aws_config else "") or ""

    if explicit_region:
        # Try the explicit region first
        result = await _search_ec2_in_region(private_ip, explicit_region, aws_config, loop)
        if result:
            return result
        log.info("aws_instance_not_in_explicit_region", region=explicit_region)

    # Auto-discover: search all available regions
    all_regions = await _discover_aws_regions(aws_config)

    # Put common regions first for faster discovery, skip already-tried region
    priority = ["ap-south-1", "us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
    ordered = [r for r in priority if r in all_regions and r != explicit_region]
    ordered += [r for r in all_regions if r not in priority and r != explicit_region]

    log.info("aws_scanning_regions", count=len(ordered))

    for r in ordered:
        result = await _search_ec2_in_region(private_ip, r, aws_config, loop)
        if result:
            log.info("aws_instance_found_in_region", region=r)
            return result

    log.warning("aws_instance_not_found", private_ip=private_ip, regions_searched=len(ordered) + (1 if explicit_region else 0))
    return None


async def _search_ec2_in_region(
    private_ip: str, region: str, aws_config: "AWSConfig | None", loop
) -> DiscoveredInstance | None:
    """Search for an EC2 instance by private IP in a specific region."""
    from app.cloud.aws_auth import get_aws_client

    try:
        client = await loop.run_in_executor(
            None,
            lambda: get_aws_client("ec2", aws_config, region=region),
        )

        response = await loop.run_in_executor(
            None,
            lambda: client.describe_instances(
                Filters=[
                    {"Name": "private-ip-address", "Values": [private_ip]},
                    {"Name": "instance-state-name", "Values": ["running", "stopped"]},
                ],
            ),
        )

        for reservation in response.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                instance_id = inst.get("InstanceId", "")
                az = inst.get("Placement", {}).get("AvailabilityZone", "")

                # Get Name tag
                name = ""
                tags = {}
                for tag in inst.get("Tags", []):
                    tags[tag["Key"]] = tag["Value"]
                    if tag["Key"] == "Name":
                        name = tag["Value"]

                discovered = DiscoveredInstance(
                    cloud="aws",
                    instance_name=name or instance_id,
                    instance_id=instance_id,
                    private_ip=private_ip,
                    zone=az,
                    region=region,
                    machine_type=inst.get("InstanceType", ""),
                    status=inst.get("State", {}).get("Name", ""),
                    network=inst.get("SubnetId", ""),
                    tags=tags,
                )

                logger.info(
                    "aws_instance_discovered",
                    instance_id=instance_id,
                    name=name,
                    region=region,
                    az=az,
                )
                return discovered

        return None

    except Exception as exc:
        logger.debug("aws_region_search_failed", region=region, error=str(exc))
        return None


async def _discover_aws_regions(aws_config: "AWSConfig | None" = None) -> list[str]:
    """Get list of enabled AWS regions. Falls back to common ones."""
    from app.cloud.aws_auth import get_aws_client

    common = ["ap-south-1", "us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
    try:
        client = get_aws_client("ec2", aws_config, region="us-east-1")
        resp = client.describe_regions(
            Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}]
        )
        return [r["RegionName"] for r in resp.get("Regions", [])]
    except Exception:
        return common


# ═══════════════════════════════════════════════════════════════════
#  Cached Discovery (uses Redis)
# ═══════════════════════════════════════════════════════════════════

async def discover_instance_cached(
    private_ip: str,
    cloud: str,
    project_id: str = "",
    region: str = "",
    sa_key_path: str = "",
    aws_profile: str = "",
    aws_config: "AWSConfig | None" = None,
    redis=None,
) -> DiscoveredInstance | None:
    """
    Discover instance with Redis caching.

    Cache key: airex:discovery:{cloud}:{private_ip}
    TTL: 1 hour
    """
    cache_key = f"airex:discovery:{cloud}:{private_ip}"

    # Check cache
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached if isinstance(cached, str) else cached.decode())
                logger.debug("discovery_cache_hit", ip=private_ip, instance=data.get("instance_name"))
                return DiscoveredInstance(**data)
        except Exception:
            pass

    # Discover
    discovered = None
    if cloud == "gcp":
        discovered = await discover_gcp_instance(
            private_ip=private_ip,
            project_id=project_id,
            sa_key_path=sa_key_path,
        )
    elif cloud == "aws":
        discovered = await discover_aws_instance(
            private_ip=private_ip,
            region=region,
            aws_config=aws_config,
        )

    # Cache result
    if discovered and redis:
        try:
            await redis.set(
                cache_key,
                json.dumps(asdict(discovered)),
                ex=DISCOVERY_CACHE_TTL,
            )
            logger.debug("discovery_cached", ip=private_ip, instance=discovered.instance_name)
        except Exception:
            pass

    return discovered
