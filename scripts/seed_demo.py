#!/usr/bin/env python3
"""
Seed script: walk through the full AIREX incident lifecycle.

Usage:
    python -m scripts.seed_demo [--base-url http://localhost:8000]

Creates a demo incident via the generic webhook, then steps through
each state transition so you can see the full pipeline in the UI.
"""

import argparse
import json
import sys
import time

import httpx

DEFAULT_BASE = "http://localhost:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000000"
DEFAULT_ORG_SLUG = "default-org"
DEFAULT_TENANT_SLUG = "default-workspace"


def main():
    parser = argparse.ArgumentParser(description="AIREX demo seed")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--org-slug", default=DEFAULT_ORG_SLUG)
    parser.add_argument("--tenant-slug", default=DEFAULT_TENANT_SLUG)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    webhook_path = f"/api/v1/webhooks/{args.org_slug}/{args.tenant_slug}/generic"

    headers = {"X-Tenant-Id": TENANT_ID, "Content-Type": "application/json"}
    client = httpx.Client(base_url=base, headers=headers, timeout=15)

    # Health check
    print("[1/6] Health check...")
    r = client.get("/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print(f"  -> {r.json()}")

    # Create incident via generic webhook
    print("\n[2/6] Creating incident via generic webhook...")
    payload = {
        "alert_type": "cpu_high",
        "severity": "HIGH",
        "title": "[DEMO] CPU spike on prod-web-03",
        "resource_id": "prod-web-03",
        "meta": {
            "host": "prod-web-03",
            "cpu_percent": 94.2,
            "process": "java -jar app.jar",
            "region": "us-east-1",
        },
    }
    r = client.post(webhook_path, json=payload)
    assert r.status_code == 202, f"Webhook failed: {r.text}"
    incident_id = r.json()["incident_id"]
    print(f"  -> Incident created: {incident_id}")

    # List incidents
    print("\n[3/6] Listing incidents...")
    r = client.get("/api/v1/incidents/")
    assert r.status_code == 200
    incidents = r.json()
    print(f"  -> {len(incidents)} incident(s) found")

    # Get incident detail
    print(f"\n[4/6] Fetching incident detail: {incident_id[:8]}...")
    r = client.get(f"/api/v1/incidents/{incident_id}")
    assert r.status_code == 200
    detail = r.json()
    print(f"  -> State: {detail['state']}")
    print(f"  -> Title: {detail['title']}")
    print(f"  -> Severity: {detail['severity']}")
    print(f"  -> Transitions: {len(detail.get('state_transitions', []))}")

    # Check metrics
    print("\n[5/6] Checking Prometheus metrics...")
    r = client.get("/metrics")
    assert r.status_code == 200
    metric_lines = [l for l in r.text.split("\n") if "airex_" in l and not l.startswith("#")]
    for line in metric_lines[:10]:
        print(f"  -> {line}")
    if len(metric_lines) > 10:
        print(f"  -> ... and {len(metric_lines) - 10} more")

    # Summary
    print("\n[6/6] Demo complete!")
    print(f"\n  Dashboard:  http://localhost:5173/incidents")
    print(f"  Detail:     http://localhost:5173/incidents/{incident_id}")
    print(f"  API Docs:   {base}/docs")
    print(f"  Metrics:    {base}/metrics")
    print(f"\n  The incident is now in INVESTIGATING state.")
    print(f"  If the ARQ worker is running, it will proceed through the pipeline automatically.")


if __name__ == "__main__":
    main()
