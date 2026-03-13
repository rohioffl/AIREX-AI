"""
Predictive analytics service.

Predicts likely root causes and recommended actions from early evidence,
using historical incident resolution data as a basis for predictions.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident

logger = structlog.get_logger()


async def predict_root_cause(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    alert_type: str,
    severity: str | None = None,
    host_key: str | None = None,
    evidence_summary: str | None = None,
) -> dict[str, Any]:
    """
    Predict likely root cause based on historical resolved incidents.

    Analyzes past incidents with the same alert_type to determine
    the most likely root cause and recommended action.
    """
    log = logger.bind(tenant_id=str(tenant_id), alert_type=alert_type)

    # Fetch historical resolved incidents of the same type
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    filters = [
        Incident.tenant_id == tenant_id,
        Incident.alert_type == alert_type,
        Incident.state == IncidentState.RESOLVED,
        Incident.created_at >= cutoff,
        Incident.deleted_at.is_(None),
    ]

    result = await session.execute(
        select(Incident).where(*filters).order_by(Incident.created_at.desc())
    )
    historical = list(result.scalars().all())

    if not historical:
        log.debug("no_historical_data")
        return {
            "prediction_available": False,
            "confidence": 0.0,
            "message": "Insufficient historical data for prediction",
        }

    # Extract root causes and actions from historical data
    root_causes: list[str] = []
    actions: list[str] = []
    resolution_times: list[float] = []
    host_matches: list[Incident] = []

    for inc in historical:
        meta = inc.meta or {}
        rec = meta.get("recommendation", {})
        rc = rec.get("root_cause")
        action = rec.get("proposed_action")
        if rc:
            root_causes.append(rc)
        if action:
            actions.append(action)
        if inc.resolution_duration_seconds:
            resolution_times.append(inc.resolution_duration_seconds)
        if host_key and inc.host_key == host_key:
            host_matches.append(inc)

    # Count frequencies
    rc_counter = Counter(root_causes)
    action_counter = Counter(actions)

    if not rc_counter:
        return {
            "prediction_available": False,
            "confidence": 0.0,
            "message": "Historical incidents lack root cause data",
        }

    # Top predictions
    top_root_cause, rc_count = rc_counter.most_common(1)[0]
    top_action = action_counter.most_common(1)[0][0] if action_counter else "manual_review"

    # Confidence based on consistency of root causes
    total_with_rc = len(root_causes)
    confidence = min(rc_count / total_with_rc, 0.95) if total_with_rc > 0 else 0.0

    # Boost confidence if host matches exist
    if host_matches:
        host_rc = Counter()
        for inc in host_matches:
            meta = inc.meta or {}
            rc = meta.get("recommendation", {}).get("root_cause")
            if rc:
                host_rc[rc] += 1
        if host_rc and host_rc.most_common(1)[0][0] == top_root_cause:
            confidence = min(confidence + 0.1, 0.95)

    # Estimated resolution time
    avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else None

    # Build prediction response
    predictions = []
    for rc, count in rc_counter.most_common(5):
        pct = count / total_with_rc
        # Find most common action for this root cause
        rc_actions = []
        for inc in historical:
            meta = inc.meta or {}
            rec = meta.get("recommendation", {})
            if rec.get("root_cause") == rc and rec.get("proposed_action"):
                rc_actions.append(rec["proposed_action"])
        best_action = Counter(rc_actions).most_common(1)[0][0] if rc_actions else "manual_review"

        predictions.append({
            "root_cause": rc,
            "probability": round(pct, 3),
            "recommended_action": best_action,
            "historical_count": count,
        })

    log.info(
        "prediction_generated",
        top_root_cause=top_root_cause,
        confidence=round(confidence, 3),
        historical_count=len(historical),
    )

    return {
        "prediction_available": True,
        "confidence": round(confidence, 3),
        "top_prediction": {
            "root_cause": top_root_cause,
            "recommended_action": top_action,
            "historical_occurrences": rc_count,
        },
        "all_predictions": predictions,
        "estimated_resolution_seconds": round(avg_resolution) if avg_resolution else None,
        "historical_incident_count": len(historical),
        "host_specific_matches": len(host_matches),
    }


async def get_prediction_accuracy(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    days: int = 30,
) -> dict[str, Any]:
    """
    Evaluate prediction accuracy by comparing predictions against actual outcomes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.state == IncidentState.RESOLVED,
            Incident.created_at >= cutoff,
            Incident.deleted_at.is_(None),
        )
    )
    incidents = list(result.scalars().all())

    if not incidents:
        return {"accuracy": 0.0, "sample_size": 0}

    correct = 0
    total = 0
    for inc in incidents:
        meta = inc.meta or {}
        predicted = meta.get("_predicted_root_cause")
        actual = meta.get("recommendation", {}).get("root_cause")
        if predicted and actual:
            total += 1
            if predicted.lower().strip() == actual.lower().strip():
                correct += 1

    accuracy = correct / total if total > 0 else 0.0
    return {
        "accuracy": round(accuracy, 3),
        "correct_predictions": correct,
        "total_predictions": total,
        "sample_size": len(incidents),
        "period_days": days,
    }
