"""Report generation service for scheduled and on-demand reports."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident
from airex_core.models.report_template import ReportTemplate

logger = structlog.get_logger()


async def generate_report_from_template(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    template: ReportTemplate,
) -> dict[str, Any]:
    """
    Generate a report based on a template's filters.
    
    Returns a dictionary with report data including:
    - Summary statistics
    - Incident list
    - Trends (if date range specified)
    """
    filters = template.filters or {}
    
    # Build query
    query = select(Incident).where(
        Incident.tenant_id == tenant_id,
        Incident.deleted_at.is_(None),
    )
    
    # Apply filters
    if filters.get("state"):
        query = query.where(Incident.state == IncidentState(filters["state"]))
    
    if filters.get("severity"):
        query = query.where(Incident.severity == SeverityLevel(filters["severity"]))
    
    if filters.get("alert_type"):
        query = query.where(Incident.alert_type == filters["alert_type"])
    
    if filters.get("host_key"):
        query = query.where(Incident.host_key == filters["host_key"])
    
    # Date range filter
    if filters.get("date_from") or filters.get("date_to"):
        if filters.get("date_from"):
            date_from = datetime.fromisoformat(filters["date_from"].replace("Z", "+00:00"))
            query = query.where(Incident.created_at >= date_from)
        if filters.get("date_to"):
            date_to = datetime.fromisoformat(filters["date_to"].replace("Z", "+00:00"))
            query = query.where(Incident.created_at <= date_to)
    else:
        # Default to last 30 days if no date range
        date_from = datetime.now(timezone.utc) - timedelta(days=30)
        query = query.where(Incident.created_at >= date_from)
    
    # Order by created_at desc
    query = query.order_by(Incident.created_at.desc())
    
    # Execute query
    result = await session.execute(query)
    incidents = result.scalars().all()
    
    # Calculate statistics
    total_incidents = len(incidents)
    by_state = {}
    by_severity = {}
    by_alert_type = {}
    
    for incident in incidents:
        # Count by state
        state_key = incident.state.value
        by_state[state_key] = by_state.get(state_key, 0) + 1
        
        # Count by severity
        severity_key = incident.severity.value
        by_severity[severity_key] = by_severity.get(severity_key, 0) + 1
        
        # Count by alert type
        alert_type_key = incident.alert_type
        by_alert_type[alert_type_key] = by_alert_type.get(alert_type_key, 0) + 1
    
    # Calculate MTTR (Mean Time To Resolution)
    resolved_incidents = [i for i in incidents if i.state == IncidentState.RESOLVED and i.resolved_at]
    mttr_seconds = None
    if resolved_incidents:
        total_resolution_time = sum(
            (i.resolved_at - i.created_at).total_seconds()
            for i in resolved_incidents
        )
        mttr_seconds = total_resolution_time / len(resolved_incidents)
    
    # Build report data
    report_data = {
        "template_name": template.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {
            "from": filters.get("date_from") or (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "to": filters.get("date_to") or datetime.now(timezone.utc).isoformat(),
        },
        "summary": {
            "total_incidents": total_incidents,
            "by_state": by_state,
            "by_severity": by_severity,
            "by_alert_type": by_alert_type,
            "mttr_seconds": mttr_seconds,
            "resolved_count": len(resolved_incidents),
        },
        "incidents": [
            {
                "id": str(incident.id),
                "title": incident.title,
                "state": incident.state.value,
                "severity": incident.severity.value,
                "alert_type": incident.alert_type,
                "host_key": incident.host_key,
                "created_at": incident.created_at.isoformat(),
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            }
            for incident in incidents[:1000]  # Limit to 1000 incidents
        ],
    }
    
    logger.info(
        "report_generated",
        tenant_id=str(tenant_id),
        template_id=str(template.id),
        total_incidents=total_incidents,
    )
    
    return report_data
