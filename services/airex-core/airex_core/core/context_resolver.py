"""
Phase 3e: Execution Context Resolver.

Transforms raw incident meta / snapshot params into a structured
ExecutionContext that action classes can rely on for deterministic
targeting — no more ad-hoc dict key guessing inside each action.

Design principles:
- Pure function: no I/O, no Redis, no cloud API calls.
- Deterministic: same params -> same context every time.
- Non-blocking: safe to call from async code via normal function call.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger()


@dataclass
class ExecutionContext:
    """Resolved execution target context.

    Attributes:
        cloud:        Cloud provider ("aws" | "gcp" | "unknown").
        instance_id:  EC2 instance ID (i-xxxx) or GCE instance name.
        region:       AWS region or GCP region (e.g. "ap-south-1").
        zone:         Availability zone (e.g. "ap-south-1a" / "asia-south1-a").
        exec_mode:    How the action will reach the target:
                        "ssm"  — AWS SSM RunShellScript
                        "ssh"  — GCP OS Login / EC2 Instance Connect SSH
                        "sim"  — simulation (no live target found)
        environment:  Deployment environment ("prod" | "staging" | "dev" |
                      "unknown").  Sourced from params["_environment"].
        namespace:    Kubernetes namespace (empty if not applicable).
        cluster:      Kubernetes cluster name (empty if not applicable).
        service_name: Application / service name for the affected workload.
        tenant_name:  Tenant name used to look up cloud credentials.
    """

    cloud: str = "unknown"
    instance_id: str = ""
    region: str = ""
    zone: str = ""
    exec_mode: str = "sim"
    environment: str = "unknown"
    namespace: str = ""
    cluster: str = ""
    service_name: str = ""
    tenant_name: str = ""


def resolve_execution_context(params: dict) -> ExecutionContext:
    """Resolve a flat params dict into a structured ExecutionContext.

    Reads both underscore-prefixed keys (e.g. ``_cloud``) set by the
    investigation pipeline and plain keys (e.g. ``cloud``) that may come
    from manual meta.  Underscore-prefixed keys take precedence.

    Args:
        params: The frozen execution snapshot params dict (or live meta
                as fallback). Must not be None — pass ``{}`` if empty.

    Returns:
        ExecutionContext with all resolvable fields populated.
    """
    def _get(primary: str, fallback: str = "") -> str:
        v = params.get(primary) or params.get(primary.lstrip("_")) or ""
        if not v and fallback:
            v = params.get(fallback) or ""
        return str(v).strip()

    cloud = _get("_cloud").lower() or "unknown"
    instance_id = _get("_instance_id")
    region = _get("_region")
    zone = _get("_zone", "_gcp_zone")
    environment = _get("_environment").lower() or "unknown"
    namespace = _get("_namespace")
    cluster = _get("_cluster")
    service_name = _get("service_name")
    tenant_name = _get("_tenant_name")

    # Determine execution mode from available identifiers
    if cloud == "aws" and instance_id:
        exec_mode = "ssm"
    elif cloud == "gcp" and instance_id:
        exec_mode = "ssh"
    else:
        exec_mode = "sim"

    ctx = ExecutionContext(
        cloud=cloud,
        instance_id=instance_id,
        region=region,
        zone=zone,
        exec_mode=exec_mode,
        environment=environment,
        namespace=namespace,
        cluster=cluster,
        service_name=service_name,
        tenant_name=tenant_name,
    )

    logger.info(
        "execution_context_resolved",
        cloud=ctx.cloud,
        exec_mode=ctx.exec_mode,
        environment=ctx.environment,
        has_instance=bool(instance_id),
        has_region=bool(region),
    )

    return ctx
