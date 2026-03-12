"""
API endpoints for Grafana dashboard export/import.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, TenantId, TenantSession, require_permission
from airex_core.core.rbac import Permission

logger = structlog.get_logger()
router = APIRouter()


# ── In-memory storage for dashboard configs (backed by incident meta in production) ──

class GrafanaDashboardExport(BaseModel):
    """Exported Grafana dashboard JSON."""
    title: str
    dashboard_json: dict[str, Any]
    datasource_overrides: dict[str, str] | None = None
    folder: str | None = None
    tags: list[str] | None = None


class GrafanaDashboardImportRequest(BaseModel):
    """Request to import a Grafana dashboard."""
    grafana_url: str = Field(..., description="Grafana instance URL")
    api_key: str = Field(..., description="Grafana API key")
    dashboard_uid: str = Field(..., description="Dashboard UID to import")
    folder_id: int | None = None


class DashboardTemplate(BaseModel):
    """Pre-built dashboard template for AIREX metrics."""
    id: str
    name: str
    description: str
    category: str
    panels: list[dict[str, Any]]
    variables: list[dict[str, Any]]


# ── Pre-built AIREX dashboard templates ──

AIREX_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "airex-incident-overview",
        "name": "AIREX Incident Overview",
        "description": "Real-time incident status, severity distribution, and state breakdown",
        "category": "incidents",
        "panels": [
            {
                "title": "Active Incidents",
                "type": "stat",
                "targets": [{"expr": 'count(airex_incidents_active{tenant_id="$tenant_id"})'}],
            },
            {
                "title": "Incidents by Severity",
                "type": "piechart",
                "targets": [{"expr": 'sum by(severity) (airex_incidents_total{tenant_id="$tenant_id"})'}],
            },
            {
                "title": "Incident Rate (24h)",
                "type": "timeseries",
                "targets": [{"expr": 'rate(airex_incidents_created_total{tenant_id="$tenant_id"}[1h])'}],
            },
            {
                "title": "State Distribution",
                "type": "bargauge",
                "targets": [{"expr": 'sum by(state) (airex_incidents_total{tenant_id="$tenant_id"})'}],
            },
        ],
        "variables": [
            {"name": "tenant_id", "type": "constant", "default": "00000000-0000-0000-0000-000000000000"},
            {"name": "interval", "type": "interval", "default": "1h"},
        ],
    },
    {
        "id": "airex-ai-performance",
        "name": "AIREX AI Performance",
        "description": "AI recommendation accuracy, confidence scores, and processing times",
        "category": "ai",
        "panels": [
            {
                "title": "AI Confidence Score",
                "type": "gauge",
                "targets": [{"expr": 'avg(airex_ai_confidence{tenant_id="$tenant_id"})'}],
            },
            {
                "title": "Recommendation Success Rate",
                "type": "stat",
                "targets": [{"expr": 'sum(airex_recommendations_approved) / sum(airex_recommendations_total)'}],
            },
            {
                "title": "LLM Response Time",
                "type": "timeseries",
                "targets": [{"expr": 'histogram_quantile(0.95, rate(airex_llm_duration_seconds_bucket[5m]))'}],
            },
            {
                "title": "Investigation Duration",
                "type": "timeseries",
                "targets": [{"expr": 'avg(airex_investigation_duration_seconds{tenant_id="$tenant_id"})'}],
            },
        ],
        "variables": [
            {"name": "tenant_id", "type": "constant", "default": "00000000-0000-0000-0000-000000000000"},
        ],
    },
    {
        "id": "airex-mttr-analytics",
        "name": "AIREX MTTR Analytics",
        "description": "Mean Time to Resolution trends, resolution types, and SLA compliance",
        "category": "analytics",
        "panels": [
            {
                "title": "MTTR Trend",
                "type": "timeseries",
                "targets": [{"expr": 'avg_over_time(airex_mttr_seconds{tenant_id="$tenant_id"}[1d])'}],
            },
            {
                "title": "Resolution Type Breakdown",
                "type": "piechart",
                "targets": [{"expr": 'sum by(resolution_type) (airex_resolved_total{tenant_id="$tenant_id"})'}],
            },
            {
                "title": "P50 / P95 / P99 Resolution Time",
                "type": "timeseries",
                "targets": [
                    {"expr": 'histogram_quantile(0.5, rate(airex_resolution_seconds_bucket[1h]))', "legendFormat": "P50"},
                    {"expr": 'histogram_quantile(0.95, rate(airex_resolution_seconds_bucket[1h]))', "legendFormat": "P95"},
                    {"expr": 'histogram_quantile(0.99, rate(airex_resolution_seconds_bucket[1h]))', "legendFormat": "P99"},
                ],
            },
        ],
        "variables": [
            {"name": "tenant_id", "type": "constant", "default": "00000000-0000-0000-0000-000000000000"},
            {"name": "interval", "type": "interval", "default": "1d"},
        ],
    },
    {
        "id": "airex-anomaly-monitor",
        "name": "AIREX Anomaly Monitor",
        "description": "Real-time anomaly detection metrics and alert patterns",
        "category": "monitoring",
        "panels": [
            {
                "title": "Anomaly Score",
                "type": "gauge",
                "targets": [{"expr": 'airex_anomaly_score{tenant_id="$tenant_id"}'}],
            },
            {
                "title": "Incident Frequency vs Baseline",
                "type": "timeseries",
                "targets": [
                    {"expr": 'rate(airex_incidents_created_total{tenant_id="$tenant_id"}[1h])', "legendFormat": "Current"},
                    {"expr": 'avg_over_time(rate(airex_incidents_created_total{tenant_id="$tenant_id"}[1h])[7d:])', "legendFormat": "7d Baseline"},
                ],
            },
            {
                "title": "Critical Incident Ratio",
                "type": "timeseries",
                "targets": [{"expr": 'sum(airex_incidents_active{severity="CRITICAL"}) / sum(airex_incidents_active)'}],
            },
        ],
        "variables": [
            {"name": "tenant_id", "type": "constant", "default": "00000000-0000-0000-0000-000000000000"},
        ],
    },
]


def _build_grafana_dashboard_json(template: dict[str, Any], datasource: str = "Prometheus") -> dict[str, Any]:
    """Convert an AIREX template to a valid Grafana dashboard JSON."""
    panels = []
    for idx, panel in enumerate(template["panels"]):
        panels.append({
            "id": idx + 1,
            "title": panel["title"],
            "type": panel["type"],
            "gridPos": {"h": 8, "w": 12, "x": (idx % 2) * 12, "y": (idx // 2) * 8},
            "targets": [
                {**t, "datasource": {"type": "prometheus", "uid": datasource}}
                for t in panel.get("targets", [])
            ],
            "fieldConfig": {"defaults": {}, "overrides": []},
            "options": {},
        })

    templating_list = []
    for var in template.get("variables", []):
        templating_list.append({
            "name": var["name"],
            "type": var["type"],
            "current": {"value": var.get("default", "")},
        })

    return {
        "dashboard": {
            "id": None,
            "uid": template["id"],
            "title": template["name"],
            "description": template["description"],
            "tags": ["airex", template["category"]],
            "timezone": "utc",
            "schemaVersion": 39,
            "version": 1,
            "panels": panels,
            "templating": {"list": templating_list},
            "time": {"from": "now-24h", "to": "now"},
            "refresh": "30s",
        },
        "overwrite": True,
    }


# ── Endpoints ────────────────────────────────────────────────

@router.get("/templates")
async def list_dashboard_templates(
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
    category: str | None = Query(None, description="Filter by category"),
):
    """List available AIREX Grafana dashboard templates."""
    templates = AIREX_TEMPLATES
    if category:
        templates = [t for t in templates if t["category"] == category]
    return {"templates": templates, "total": len(templates)}


@router.get("/templates/{template_id}")
async def get_dashboard_template(
    template_id: str,
    current_user: CurrentUser,
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Get a specific dashboard template."""
    template = next((t for t in AIREX_TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.post("/templates/{template_id}/export")
async def export_dashboard(
    template_id: str,
    current_user: CurrentUser,
    datasource: str = Query("Prometheus", description="Grafana datasource name"),
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Export an AIREX dashboard template as Grafana-compatible JSON."""
    template = next((t for t in AIREX_TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    dashboard_json = _build_grafana_dashboard_json(template, datasource)
    return {
        "grafana_dashboard": dashboard_json,
        "instructions": {
            "import_url": "/api/dashboards/db",
            "method": "POST",
            "headers": {"Authorization": "Bearer <your-grafana-api-key>", "Content-Type": "application/json"},
            "note": "POST this JSON to your Grafana instance's /api/dashboards/db endpoint",
        },
    }


@router.post("/export-all")
async def export_all_dashboards(
    current_user: CurrentUser,
    datasource: str = Query("Prometheus", description="Grafana datasource name"),
    _perm: None = Depends(require_permission(Permission.INCIDENT_VIEW)),
):
    """Export all AIREX dashboard templates as Grafana-compatible JSON."""
    dashboards = []
    for template in AIREX_TEMPLATES:
        dashboards.append({
            "template_id": template["id"],
            "name": template["name"],
            "grafana_dashboard": _build_grafana_dashboard_json(template, datasource),
        })
    return {"dashboards": dashboards, "total": len(dashboards)}
