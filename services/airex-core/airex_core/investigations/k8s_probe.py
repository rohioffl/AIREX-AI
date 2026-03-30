"""Kubernetes status probe for pod/deployment level incidents."""

from __future__ import annotations

import time

from airex_core.investigations.base import (
    Anomaly,
    BaseInvestigation,
    InvestigationResult,
    ProbeCategory,
    ProbeResult,
    _make_seeded_rng,
)


def should_run_k8s_status_probe(meta: dict) -> bool:
    """Return True when incident metadata points to a Kubernetes resource."""

    if str(meta.get("_platform") or meta.get("platform") or "").lower() in {"k8s", "kubernetes"}:
        return True
    return bool(
        meta.get("_k8s_namespace")
        or meta.get("namespace")
        or meta.get("_k8s_pod")
        or meta.get("pod_name")
        or meta.get("_k8s_deployment")
        or meta.get("deployment_name")
    )


class K8sStatusProbe(BaseInvestigation):
    """Collect pod and deployment status using deterministic k8s-aware diagnostics."""

    alert_type = "k8s_status"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(incident_meta)
        namespace = (
            incident_meta.get("_k8s_namespace")
            or incident_meta.get("namespace")
            or "default"
        )
        deployment = (
            incident_meta.get("_k8s_deployment")
            or incident_meta.get("deployment_name")
            or incident_meta.get("service_name")
            or "application"
        )
        pod = (
            incident_meta.get("_k8s_pod")
            or incident_meta.get("pod_name")
            or f"{deployment}-{rng.randint(1000, 9999)}"
        )
        cluster = incident_meta.get("_k8s_cluster") or incident_meta.get("cluster_name") or "unknown-cluster"

        desired_replicas = int(incident_meta.get("desired_replicas") or rng.randint(2, 4))
        unavailable_replicas = int(incident_meta.get("unavailable_replicas") or rng.randint(0, 1))
        ready_replicas = max(desired_replicas - unavailable_replicas, 0)
        restart_count = int(incident_meta.get("restart_count") or rng.randint(0, 5))
        pod_phase = "CrashLoopBackOff" if restart_count >= 3 else "Running"
        cpu_pct = round(float(incident_meta.get("cpu_percent") or rng.uniform(72, 96)), 1)

        start = time.monotonic()
        output = [
            f"=== Kubernetes Status: {deployment} ===",
            f"Cluster: {cluster}",
            f"Namespace: {namespace}",
            f"Deployment: {deployment}",
            f"Pod: {pod}",
            f"Pod Phase: {pod_phase}",
            f"Ready Replicas: {ready_replicas}/{desired_replicas}",
            f"Restart Count: {restart_count}",
            f"Pod CPU: {cpu_pct}%",
            f"Diagnosis: Deployment {deployment} in namespace {namespace} has pod {pod} with {restart_count} restart(s)",
        ]
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        anomalies: list[Anomaly] = []
        if restart_count > 0:
            anomalies.append(
                Anomaly(
                    metric_name="pod_restarts",
                    value=float(restart_count),
                    threshold=0.0,
                    severity="critical" if restart_count >= 3 else "warning",
                    description=f"Pod {pod} restarted {restart_count} time(s)",
                )
            )
        if unavailable_replicas > 0:
            anomalies.append(
                Anomaly(
                    metric_name="unavailable_replicas",
                    value=float(unavailable_replicas),
                    threshold=0.0,
                    severity="warning",
                    description=f"Deployment {deployment} has {unavailable_replicas} unavailable replica(s)",
                )
            )

        return ProbeResult(
            tool_name="k8s_status",
            raw_output="\n".join(output),
            category=ProbeCategory.INFRASTRUCTURE,
            metrics={
                "cluster": cluster,
                "namespace": namespace,
                "deployment": deployment,
                "pod": pod,
                "ready_replicas": ready_replicas,
                "desired_replicas": desired_replicas,
                "unavailable_replicas": unavailable_replicas,
                "restart_count": restart_count,
                "pod_cpu_percent": cpu_pct,
                "pod_phase": pod_phase,
            },
            anomalies=anomalies,
            duration_ms=duration_ms,
            probe_type="secondary",
        )


__all__ = ["K8sStatusProbe", "should_run_k8s_status_probe"]
