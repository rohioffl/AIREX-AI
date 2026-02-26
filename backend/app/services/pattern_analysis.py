"""
Pattern analysis service for human-like incident analysis.

Detects trends, correlations, recurring issues, and temporal patterns
to provide context-aware recommendations like a human SRE analyst.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IncidentState, SeverityLevel
from app.models.incident import Incident

logger = structlog.get_logger()


@dataclass(frozen=True)
class PatternInsight:
    """A detected pattern or trend."""
    pattern_type: str  # "recurring", "trending", "temporal", "correlation"
    description: str
    confidence: float  # 0.0 to 1.0
    evidence: str  # Supporting data


@dataclass(frozen=True)
class PatternAnalysis:
    """Complete pattern analysis for an incident."""
    host_patterns: list[PatternInsight]
    alert_type_patterns: list[PatternInsight]
    temporal_patterns: list[PatternInsight]
    correlation_patterns: list[PatternInsight]
    historical_context: str  # Formatted summary for LLM


async def analyze_patterns(
    session: AsyncSession,
    incident: Incident,
    lookback_days: int = 30,
) -> PatternAnalysis:
    """
    Analyze patterns for an incident like a human SRE analyst.
    
    Detects:
    - Recurring issues on the same host
    - Trending alert types
    - Temporal patterns (time of day, day of week)
    - Correlations between alert types
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        alert_type=incident.alert_type,
    )
    
    now = datetime.now(timezone.utc)
    lookback_start = now - timedelta(days=lookback_days)
    
    # Query historical incidents
    base_query = (
        select(Incident)
        .where(
            Incident.tenant_id == incident.tenant_id,
            Incident.deleted_at.is_(None),
            Incident.id != incident.id,  # Exclude current incident
            Incident.created_at >= lookback_start,
        )
    )
    
    result = await session.execute(base_query)
    historical = list(result.scalars().all())
    
    if not historical:
        log.info("no_historical_data", lookback_days=lookback_days)
        return PatternAnalysis(
            host_patterns=[],
            alert_type_patterns=[],
            temporal_patterns=[],
            correlation_patterns=[],
            historical_context="No historical incidents found in the last 30 days.",
        )
    
    # Analyze patterns
    host_patterns = _analyze_host_patterns(incident, historical)
    alert_type_patterns = _analyze_alert_type_patterns(incident, historical)
    temporal_patterns = _analyze_temporal_patterns(incident, historical)
    correlation_patterns = _analyze_correlation_patterns(incident, historical)
    
    # Build human-readable context
    context = _build_pattern_context(
        incident,
        historical,
        host_patterns,
        alert_type_patterns,
        temporal_patterns,
        correlation_patterns,
    )
    
    log.info(
        "pattern_analysis_complete",
        host_patterns=len(host_patterns),
        alert_patterns=len(alert_type_patterns),
        temporal_patterns=len(temporal_patterns),
        correlation_patterns=len(correlation_patterns),
    )
    
    return PatternAnalysis(
        host_patterns=host_patterns,
        alert_type_patterns=alert_type_patterns,
        temporal_patterns=temporal_patterns,
        correlation_patterns=correlation_patterns,
        historical_context=context,
    )


def _analyze_host_patterns(
    incident: Incident,
    historical: Sequence[Incident],
) -> list[PatternInsight]:
    """Detect patterns specific to the host."""
    insights = []
    
    if not incident.host_key:
        return insights
    
    # Find incidents on the same host
    host_incidents = [
        i for i in historical
        if i.host_key == incident.host_key
    ]
    
    if not host_incidents:
        return insights
    
    # Pattern: Recurring issues on this host
    same_alert_count = sum(
        1 for i in host_incidents
        if i.alert_type == incident.alert_type
    )
    
    if same_alert_count >= 3:
        insights.append(PatternInsight(
            pattern_type="recurring",
            description=(
                f"This host has experienced {same_alert_count} similar "
                f"'{incident.alert_type}' incidents in the last 30 days. "
                f"This suggests a systemic issue rather than a one-time event."
            ),
            confidence=min(0.9, 0.5 + (same_alert_count * 0.1)),
            evidence=f"{same_alert_count} incidents of type '{incident.alert_type}' on this host",
        ))
    
    # Pattern: Multiple alert types on same host (indicates instability)
    unique_alert_types = len(set(i.alert_type for i in host_incidents))
    if unique_alert_types >= 4:
        insights.append(PatternInsight(
            pattern_type="trending",
            description=(
                f"This host is experiencing multiple types of incidents "
                f"({unique_alert_types} different alert types). This indicates "
                f"general system instability or resource exhaustion."
            ),
            confidence=0.75,
            evidence=f"{unique_alert_types} different alert types on this host",
        ))
    
    # Pattern: Resolution patterns
    resolved_count = sum(
        1 for i in host_incidents
        if i.state == IncidentState.RESOLVED
    )
    if resolved_count > 0:
        # Check what actions were successful
        successful_actions = []
        for i in host_incidents:
            if i.state == IncidentState.RESOLVED and i.meta:
                rec = i.meta.get("recommendation", {})
                if rec and rec.get("proposed_action"):
                    successful_actions.append(rec["proposed_action"])
        
        if successful_actions:
            action_counts = Counter(successful_actions)
            most_common = action_counts.most_common(1)[0]
            if most_common[1] >= 2:
                insights.append(PatternInsight(
                    pattern_type="correlation",
                    description=(
                        f"On this host, '{most_common[0]}' has successfully "
                        f"resolved {most_common[1]} similar incidents. "
                        f"This action has a proven track record here."
                    ),
                    confidence=0.8,
                    evidence=f"Action '{most_common[0]}' resolved {most_common[1]} incidents",
                ))
    
    return insights


def _analyze_alert_type_patterns(
    incident: Incident,
    historical: Sequence[Incident],
) -> list[PatternInsight]:
    """Detect patterns for this alert type across all hosts."""
    insights = []
    
    # Find incidents with same alert type
    same_type = [
        i for i in historical
        if i.alert_type == incident.alert_type
    ]
    
    if not same_type:
        return insights
    
    # Pattern: Trending alert type
    if len(same_type) >= 5:
        # Check if frequency is increasing
        recent_count = sum(
            1 for i in same_type
            if i.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        )
        older_count = len(same_type) - recent_count
        
        if recent_count > older_count * 1.5:
            insights.append(PatternInsight(
                pattern_type="trending",
                description=(
                    f"'{incident.alert_type}' incidents are trending upward. "
                    f"{recent_count} incidents in the last 7 days vs "
                    f"{older_count} in the previous 23 days. "
                    f"This may indicate a broader infrastructure issue."
                ),
                confidence=0.85,
                evidence=f"{recent_count} recent vs {older_count} older incidents",
            ))
    
    # Pattern: Common resolution for this alert type
    resolved = [
        i for i in same_type
        if i.state == IncidentState.RESOLVED
    ]
    
    if resolved:
        successful_actions = []
        for i in resolved:
            if i.meta:
                rec = i.meta.get("recommendation", {})
                if rec and rec.get("proposed_action"):
                    successful_actions.append(rec["proposed_action"])
        
        if successful_actions:
            action_counts = Counter(successful_actions)
            most_common = action_counts.most_common(1)[0]
            total_resolved = len(resolved)
            success_rate = most_common[1] / total_resolved
            
            if success_rate >= 0.5 and most_common[1] >= 3:
                insights.append(PatternInsight(
                    pattern_type="correlation",
                    description=(
                        f"For '{incident.alert_type}' incidents, "
                        f"'{most_common[0]}' has been the successful action "
                        f"in {most_common[1]} out of {total_resolved} resolved cases "
                        f"({success_rate:.0%} success rate). This is a proven solution."
                    ),
                    confidence=min(0.9, 0.6 + (success_rate * 0.3)),
                    evidence=f"{most_common[1]}/{total_resolved} resolved with '{most_common[0]}'",
                ))
    
    return insights


def _analyze_temporal_patterns(
    incident: Incident,
    historical: Sequence[Incident],
) -> list[PatternInsight]:
    """Detect time-based patterns."""
    insights = []
    
    if not historical:
        return insights
    
    # Group by hour of day
    hour_counts = Counter(i.created_at.hour for i in historical)
    if hour_counts:
        most_common_hour = hour_counts.most_common(1)[0]
        if most_common_hour[1] >= 3:
            insights.append(PatternInsight(
                pattern_type="temporal",
                description=(
                    f"Incidents frequently occur around {most_common_hour[0]}:00 UTC "
                    f"({most_common_hour[1]} incidents). This suggests a scheduled job, "
                    f"traffic pattern, or recurring maintenance window."
                ),
                confidence=0.7,
                evidence=f"{most_common_hour[1]} incidents at {most_common_hour[0]}:00 UTC",
            ))
    
    # Group by day of week
    weekday_counts = Counter(i.created_at.weekday() for i in historical)
    if weekday_counts:
        most_common_day = weekday_counts.most_common(1)[0]
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if most_common_day[1] >= 3:
            insights.append(PatternInsight(
                pattern_type="temporal",
                description=(
                    f"Incidents frequently occur on {day_names[most_common_day[0]]} "
                    f"({most_common_day[1]} incidents). This may correlate with "
                    f"weekly deployment cycles or traffic patterns."
                ),
                confidence=0.65,
                evidence=f"{most_common_day[1]} incidents on {day_names[most_common_day[0]]}",
            ))
    
    return insights


def _analyze_correlation_patterns(
    incident: Incident,
    historical: Sequence[Incident],
) -> list[PatternInsight]:
    """Detect correlations between different alert types."""
    insights = []
    
    if not incident.host_key:
        return insights
    
    # Find incidents on same host
    host_incidents = [
        i for i in historical
        if i.host_key == incident.host_key
    ]
    
    if len(host_incidents) < 3:
        return insights
    
    # Check for alert type co-occurrence
    alert_types = [i.alert_type for i in host_incidents]
    alert_type_counts = Counter(alert_types)
    
    # Find alert types that often occur together
    if incident.alert_type in alert_type_counts:
        # Look for other alert types that appear frequently with this one
        other_types = [
            at for at, count in alert_type_counts.items()
            if at != incident.alert_type and count >= 2
        ]
        
        if other_types:
            insights.append(PatternInsight(
                pattern_type="correlation",
                description=(
                    f"On this host, '{incident.alert_type}' often co-occurs with "
                    f"other alert types: {', '.join(other_types[:3])}. "
                    f"This suggests cascading failures or resource contention."
                ),
                confidence=0.7,
                evidence=f"Multiple alert types on same host: {', '.join(other_types[:3])}",
            ))
    
    return insights


def _build_pattern_context(
    incident: Incident,
    historical: Sequence[Incident],
    host_patterns: list[PatternInsight],
    alert_type_patterns: list[PatternInsight],
    temporal_patterns: list[PatternInsight],
    correlation_patterns: list[PatternInsight],
) -> str:
    """Build human-readable pattern context for LLM."""
    lines = ["=== Pattern Analysis (Human-like SRE Insights) ===\n"]
    
    # Summary statistics
    total_historical = len(historical)
    same_host = len([i for i in historical if i.host_key == incident.host_key])
    same_type = len([i for i in historical if i.alert_type == incident.alert_type])
    
    lines.append(f"Historical Context:")
    lines.append(f"- Total incidents in last 30 days: {total_historical}")
    if same_host > 0:
        lines.append(f"- Incidents on this host: {same_host}")
    if same_type > 0:
        lines.append(f"- Incidents of type '{incident.alert_type}': {same_type}")
    lines.append("")
    
    # Host patterns
    if host_patterns:
        lines.append("Host-Specific Patterns:")
        for pattern in host_patterns:
            lines.append(f"  • {pattern.description}")
        lines.append("")
    
    # Alert type patterns
    if alert_type_patterns:
        lines.append("Alert Type Patterns:")
        for pattern in alert_type_patterns:
            lines.append(f"  • {pattern.description}")
        lines.append("")
    
    # Temporal patterns
    if temporal_patterns:
        lines.append("Temporal Patterns:")
        for pattern in temporal_patterns:
            lines.append(f"  • {pattern.description}")
        lines.append("")
    
    # Correlation patterns
    if correlation_patterns:
        lines.append("Correlation Patterns:")
        for pattern in correlation_patterns:
            lines.append(f"  • {pattern.description}")
        lines.append("")
    
    # Recent similar incidents
    if same_type:
        recent_same_type = [
            i for i in historical
            if i.alert_type == incident.alert_type
            and i.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        ]
        if recent_same_type:
            lines.append(f"Recent Similar Incidents (last 7 days): {len(recent_same_type)}")
            for i in recent_same_type[:3]:
                state_str = i.state.value
                lines.append(f"  - {i.title[:60]}... ({state_str})")
            lines.append("")
    
    return "\n".join(lines)


__all__ = ["PatternAnalysis", "PatternInsight", "analyze_patterns"]
