"""
Enhanced log analysis probe.

Queries existing CloudWatch / Cloud Logging log sources but adds
deeper analysis on top of the raw logs:
  - Error pattern extraction (regex grouping of common error signatures)
  - Volume spike detection (compare current window vs baseline)
  - 5-minute time bucket grouping (identify when errors started)
  - First occurrence detection (find the earliest error in the window)

Runs as an automatic secondary probe for application/log-related alerts.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

from app.investigations.base import (
    Anomaly,
    BaseInvestigation,
    InvestigationResult,
    ProbeCategory,
    ProbeResult,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Common error patterns to extract from log lines
# ---------------------------------------------------------------------------

_ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OOM Kill", re.compile(r"(Out of memory|OOM|oom-kill|oom_kill)", re.IGNORECASE)),
    ("Segfault", re.compile(r"(segfault|segmentation fault|SIGSEGV)", re.IGNORECASE)),
    (
        "Connection Refused",
        re.compile(r"(Connection refused|ECONNREFUSED)", re.IGNORECASE),
    ),
    (
        "Connection Timeout",
        re.compile(r"(Connection timed out|ETIMEDOUT|connect timeout)", re.IGNORECASE),
    ),
    ("Connection Reset", re.compile(r"(Connection reset|ECONNRESET)", re.IGNORECASE)),
    (
        "Disk Full",
        re.compile(r"(No space left on device|ENOSPC|disk full)", re.IGNORECASE),
    ),
    (
        "Permission Denied",
        re.compile(r"(Permission denied|EACCES|403 Forbidden)", re.IGNORECASE),
    ),
    (
        "DNS Failure",
        re.compile(
            r"(Name or service not known|DNS resolution|NXDOMAIN|getaddrinfo)",
            re.IGNORECASE,
        ),
    ),
    (
        "SSL/TLS Error",
        re.compile(r"(SSL|TLS|certificate|handshake fail)", re.IGNORECASE),
    ),
    (
        "Database Error",
        re.compile(
            r"(deadlock|lock timeout|too many connections|connection pool)",
            re.IGNORECASE,
        ),
    ),
    (
        "HTTP 5xx",
        re.compile(
            r"(HTTP[/ ]5\d\d|status[= ]5\d\d|502 Bad Gateway|503 Service|504 Gateway)",
            re.IGNORECASE,
        ),
    ),
    (
        "HTTP 4xx",
        re.compile(
            r"(HTTP[/ ]4\d\d|status[= ]4\d\d|401 Unauthorized|404 Not Found)",
            re.IGNORECASE,
        ),
    ),
    (
        "Process Crash",
        re.compile(
            r"(core dumped|fatal error|panic|unhandled exception|traceback)",
            re.IGNORECASE,
        ),
    ),
    (
        "Service Restart",
        re.compile(
            r"(restarting|restart|service started|service stopped|systemd.*start)",
            re.IGNORECASE,
        ),
    ),
    (
        "Rate Limit",
        re.compile(r"(rate limit|throttl|too many requests|429)", re.IGNORECASE),
    ),
    (
        "Memory Pressure",
        re.compile(
            r"(memory pressure|swap|memory allocation|malloc fail)", re.IGNORECASE
        ),
    ),
    ("Kernel Error", re.compile(r"(kernel|BUG|Call Trace|RIP:)", re.IGNORECASE)),
]

# Severity keywords for classifying log lines
_SEVERITY_KEYWORDS = {
    "CRITICAL": re.compile(r"\b(CRITICAL|FATAL|EMERGENCY|EMERG)\b", re.IGNORECASE),
    "ERROR": re.compile(r"\b(ERROR|ERR|SEVERE|FAIL|FAILED)\b", re.IGNORECASE),
    "WARNING": re.compile(r"\b(WARNING|WARN|ALERT)\b", re.IGNORECASE),
}


def should_run_log_analysis(meta: dict) -> bool:
    """Check if enhanced log analysis should run.

    Runs for application and log-related alert types, or when cloud
    context is available (real logs to analyze).
    """
    alert_type = meta.get("alert_type", "")
    log_alert_types = {
        "log_anomaly",
        "healthcheck",
        "http_check",
        "api_check",
        "cpu_high",
        "memory_high",
        "database_check",
    }
    if alert_type in log_alert_types:
        return True
    # Also run when cloud logs are available
    cloud = (meta.get("_cloud") or "").lower()
    return cloud in ("aws", "gcp")


class LogAnalysisProbe(BaseInvestigation):
    """
    Enhanced log analysis that extracts patterns, detects volume
    spikes, and groups errors by time bucket.

    Works with both real cloud logs (CloudWatch / Cloud Logging) and
    simulated log evidence already stored from previous probes.
    """

    alert_type = "log_analysis"

    async def investigate(self, incident_meta: dict) -> InvestigationResult:
        cloud = (incident_meta.get("_cloud") or "").lower()
        instance_id = incident_meta.get("_instance_id", "")
        private_ip = incident_meta.get("_private_ip", "")
        host = incident_meta.get("host", instance_id or private_ip or "unknown")
        tenant_name = incident_meta.get("_tenant_name", "")

        log = logger.bind(host=host, probe="log_analysis")
        start_time = time.monotonic()

        # Fetch raw log text from cloud or use simulated
        raw_logs = await self._fetch_logs(
            cloud=cloud,
            instance_id=instance_id,
            private_ip=private_ip,
            tenant_name=tenant_name,
            incident_meta=incident_meta,
            log=log,
        )

        # Parse log lines
        lines = raw_logs.strip().split("\n") if raw_logs.strip() else []

        # Run analysis
        pattern_matches = self._extract_patterns(lines)
        severity_counts = self._count_severities(lines)
        time_buckets = self._group_by_time_bucket(lines)
        first_error = self._find_first_error(lines)
        volume_analysis = self._analyze_volume(lines, time_buckets)

        duration_ms = round((time.monotonic() - start_time) * 1000, 1)

        # Build output
        sections = self._format_output(
            host=host,
            total_lines=len(lines),
            pattern_matches=pattern_matches,
            severity_counts=severity_counts,
            time_buckets=time_buckets,
            first_error=first_error,
            volume_analysis=volume_analysis,
        )
        raw_output = "\n".join(sections)

        # Build metrics
        metrics: dict[str, Any] = {
            "total_log_lines": len(lines),
            "error_count": severity_counts.get("ERROR", 0),
            "warning_count": severity_counts.get("WARNING", 0),
            "critical_count": severity_counts.get("CRITICAL", 0),
            "pattern_count": len(pattern_matches),
            "top_pattern": pattern_matches[0][0] if pattern_matches else "none",
            "top_pattern_count": pattern_matches[0][1] if pattern_matches else 0,
            "first_error_line": first_error or "none",
            "volume_spike_detected": volume_analysis.get("spike_detected", False),
            "spike_bucket": volume_analysis.get("spike_bucket", ""),
        }

        # Build anomalies
        anomalies: list[Anomaly] = []

        error_total = severity_counts.get("ERROR", 0) + severity_counts.get(
            "CRITICAL", 0
        )
        if error_total > 5:
            anomalies.append(
                Anomaly(
                    metric_name="log_error_count",
                    value=float(error_total),
                    threshold=5.0,
                    severity="critical" if error_total > 20 else "warning",
                    description=f"{error_total} error/critical log entries detected",
                )
            )

        if volume_analysis.get("spike_detected"):
            anomalies.append(
                Anomaly(
                    metric_name="log_volume_spike",
                    value=float(volume_analysis.get("spike_ratio", 0)),
                    threshold=3.0,
                    severity="warning",
                    description=(
                        f"Log volume spike detected at {volume_analysis.get('spike_bucket', '?')} "
                        f"({volume_analysis.get('spike_ratio', 0):.1f}x baseline)"
                    ),
                )
            )

        # Flag specific critical patterns
        for pattern_name, count in pattern_matches:
            if (
                pattern_name
                in ("OOM Kill", "Segfault", "Process Crash", "Kernel Error")
                and count > 0
            ):
                anomalies.append(
                    Anomaly(
                        metric_name=f"log_pattern_{pattern_name.lower().replace(' ', '_')}",
                        value=float(count),
                        threshold=0.0,
                        severity="critical",
                        description=f"Critical log pattern '{pattern_name}' found {count} time(s)",
                    )
                )

        log.info(
            "log_analysis_complete",
            total_lines=len(lines),
            patterns=len(pattern_matches),
            errors=error_total,
            duration_ms=duration_ms,
        )

        return ProbeResult(
            tool_name="log_analysis",
            raw_output=raw_output,
            category=ProbeCategory.LOG_ANALYSIS,
            metrics=metrics,
            anomalies=anomalies,
            duration_ms=duration_ms,
            probe_type="secondary",
        )

    async def _fetch_logs(
        self,
        cloud: str,
        instance_id: str,
        private_ip: str,
        tenant_name: str,
        incident_meta: dict,
        log: structlog.stdlib.BoundLogger,
    ) -> str:
        """Fetch logs from cloud provider or generate simulated analysis input."""
        tenant_config = None
        if tenant_name:
            try:
                from app.cloud.tenant_config import get_tenant_config

                tenant_config = get_tenant_config(tenant_name)
            except Exception:
                pass

        if cloud == "aws":
            try:
                from app.cloud.aws_logs import query_cloudwatch_logs

                aws_config = tenant_config.aws if tenant_config else None
                region = incident_meta.get("_region", "")
                if not region and tenant_config:
                    region = tenant_config.aws.region
                return await query_cloudwatch_logs(
                    instance_id=instance_id,
                    region=region,
                    lookback_minutes=30,
                    aws_config=aws_config,
                )
            except Exception as exc:
                log.warning("log_analysis_aws_fetch_failed", error=str(exc))

        elif cloud == "gcp":
            try:
                from app.cloud.gcp_logging import query_gcp_logs

                project = incident_meta.get("_project", "")
                if not project and tenant_config:
                    project = tenant_config.gcp.project_id
                sa_key = tenant_config.gcp.service_account_key if tenant_config else ""
                return await query_gcp_logs(
                    project=project,
                    instance_id=instance_id,
                    private_ip=private_ip,
                    severity="WARNING",
                    lookback_minutes=30,
                    sa_key_path=sa_key,
                )
            except Exception as exc:
                log.warning("log_analysis_gcp_fetch_failed", error=str(exc))

        # Fallback: generate simulated log data for analysis demonstration
        return self._generate_simulated_logs(incident_meta)

    def _generate_simulated_logs(self, meta: dict) -> str:
        """Generate simulated log lines for analysis when no cloud is available."""
        from app.investigations.base import _make_seeded_rng

        rng = _make_seeded_rng(meta)
        alert_type = meta.get("alert_type", "unknown")
        host = meta.get("host", "unknown")

        # Generate realistic log lines based on alert type
        error_templates: dict[str, list[str]] = {
            "cpu_high": [
                f"ERROR process {rng.choice(['java', 'python', 'node'])} using {{cpu}}% CPU",
                "WARNING system load average exceeds threshold: {load}",
                "ERROR worker pool exhausted, {queued} requests queued",
                "CRITICAL CPU throttling detected on core {core}",
            ],
            "memory_high": [
                "ERROR Out of memory: Kill process {pid} ({proc})",
                "WARNING memory usage at {mem}%, swap at {swap}%",
                "ERROR malloc failed: Cannot allocate memory",
                "CRITICAL OOM killer invoked for process {proc}",
            ],
            "disk_full": [
                "ERROR No space left on device (ENOSPC)",
                "WARNING disk usage at {disk}% on /dev/{dev}",
                "ERROR write failed: No space left on device",
                "CRITICAL inode exhaustion at {inode}% on {mount}",
            ],
            "healthcheck": [
                "ERROR health check failed: HTTP {status}",
                "WARNING response time {latency}ms exceeds threshold",
                "ERROR Connection refused to upstream {host}:{port}",
                "ERROR 502 Bad Gateway from upstream server",
            ],
        }

        templates = error_templates.get(
            alert_type,
            [
                "ERROR service encountered unexpected error: {err}",
                "WARNING performance degradation detected",
                "ERROR connection timeout after {timeout}s",
            ],
        )

        lines = []
        base_time = datetime.now(timezone.utc) - timedelta(minutes=25)

        for i in range(rng.randint(15, 40)):
            ts = base_time + timedelta(seconds=rng.randint(0, 1500))
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
            template = rng.choice(templates)

            # Fill in template vars
            line = template.format(
                cpu=rng.randint(85, 99),
                load=f"{rng.uniform(8, 32):.1f}",
                queued=rng.randint(50, 500),
                core=rng.randint(0, 7),
                pid=rng.randint(1000, 65000),
                proc=rng.choice(["java", "python3", "nginx", "mysqld", "node"]),
                mem=rng.randint(88, 99),
                swap=rng.randint(50, 95),
                disk=rng.randint(92, 99),
                dev=rng.choice(["sda1", "nvme0n1p1", "xvda1"]),
                inode=rng.randint(95, 99),
                mount=rng.choice(["/", "/var", "/tmp"]),
                status=rng.choice([500, 502, 503, 504]),
                latency=rng.randint(2000, 15000),
                host=host,
                port=rng.choice([80, 443, 8080, 3000, 5432]),
                err=rng.choice(["NullPointerException", "TimeoutError", "IOError"]),
                timeout=rng.randint(15, 60),
            )
            lines.append(f"[{ts_str}] [{host}] {line}")

        lines.sort()
        return "\n".join(lines)

    def _extract_patterns(self, lines: list[str]) -> list[tuple[str, int]]:
        """Extract error pattern matches from log lines."""
        counts: dict[str, int] = {}
        for line in lines:
            for name, pattern in _ERROR_PATTERNS:
                if pattern.search(line):
                    counts[name] = counts.get(name, 0) + 1

        # Sort by frequency
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)

    def _count_severities(self, lines: list[str]) -> dict[str, int]:
        """Count log lines by severity level."""
        counts: dict[str, int] = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0, "INFO": 0}
        for line in lines:
            matched = False
            for severity, pattern in _SEVERITY_KEYWORDS.items():
                if pattern.search(line):
                    counts[severity] = counts.get(severity, 0) + 1
                    matched = True
                    break
            if not matched:
                counts["INFO"] += 1
        return counts

    def _group_by_time_bucket(self, lines: list[str]) -> list[tuple[str, int]]:
        """Group log lines into 5-minute time buckets."""
        # Try to extract timestamps from log lines
        ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2})")

        buckets: dict[str, int] = defaultdict(int)
        for line in lines:
            match = ts_pattern.search(line)
            if match:
                ts_str = match.group(1).replace("T", " ")
                try:
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                    # Round down to 5-minute bucket
                    minute_bucket = (dt.minute // 5) * 5
                    bucket_key = dt.replace(minute=minute_bucket).strftime("%H:%M")
                    buckets[bucket_key] += 1
                except ValueError:
                    continue

        return sorted(buckets.items())

    def _find_first_error(self, lines: list[str]) -> str:
        """Find the first error-level line in the logs."""
        error_pattern = re.compile(r"\b(ERROR|CRITICAL|FATAL|SEVERE)\b", re.IGNORECASE)
        for line in lines:
            if error_pattern.search(line):
                # Truncate to reasonable length
                return line[:200] if len(line) > 200 else line
        return ""

    def _analyze_volume(
        self,
        lines: list[str],
        time_buckets: list[tuple[str, int]],
    ) -> dict[str, Any]:
        """Detect volume spikes by comparing buckets to average."""
        if len(time_buckets) < 3:
            return {"spike_detected": False}

        counts = [c for _, c in time_buckets]
        avg = sum(counts) / len(counts) if counts else 0

        if avg == 0:
            return {"spike_detected": False}

        max_count = max(counts)
        max_idx = counts.index(max_count)
        spike_ratio = max_count / avg

        spike_detected = spike_ratio > 3.0 and max_count > 5

        return {
            "spike_detected": spike_detected,
            "spike_ratio": round(spike_ratio, 1),
            "spike_bucket": time_buckets[max_idx][0] if spike_detected else "",
            "spike_count": max_count if spike_detected else 0,
            "average_per_bucket": round(avg, 1),
            "bucket_count": len(time_buckets),
        }

    def _format_output(
        self,
        host: str,
        total_lines: int,
        pattern_matches: list[tuple[str, int]],
        severity_counts: dict[str, int],
        time_buckets: list[tuple[str, int]],
        first_error: str,
        volume_analysis: dict[str, Any],
    ) -> list[str]:
        """Format analysis results into human-readable text."""
        sections: list[str] = [
            f"=== Enhanced Log Analysis: {host} ===",
            f"Total log lines analyzed: {total_lines}",
            "",
        ]

        # Severity breakdown
        sections.append("--- Severity Breakdown ---")
        for sev in ("CRITICAL", "ERROR", "WARNING", "INFO"):
            count = severity_counts.get(sev, 0)
            if count > 0:
                bar = "#" * min(count, 40)
                sections.append(f"  {sev:>8}: {count:>4} {bar}")
        sections.append("")

        # Error patterns
        if pattern_matches:
            sections.append(f"--- Error Patterns ({len(pattern_matches)} types) ---")
            for name, count in pattern_matches[:10]:
                sections.append(f"  {name}: {count} occurrence(s)")
            sections.append("")

        # Volume spike
        if volume_analysis.get("spike_detected"):
            sections.append("*** LOG VOLUME SPIKE DETECTED ***")
            sections.append(
                f"  Spike at {volume_analysis['spike_bucket']}: "
                f"{volume_analysis['spike_count']} entries "
                f"({volume_analysis['spike_ratio']:.1f}x average of "
                f"{volume_analysis['average_per_bucket']:.1f}/bucket)"
            )
            sections.append("")

        # Time distribution
        if time_buckets:
            sections.append("--- Time Distribution (5-min buckets) ---")
            max_count = max(c for _, c in time_buckets) if time_buckets else 1
            for bucket, count in time_buckets:
                bar_len = int((count / max_count) * 30) if max_count > 0 else 0
                bar = "|" * bar_len
                sections.append(f"  {bucket}: {count:>4} {bar}")
            sections.append("")

        # First error
        if first_error:
            sections.append("--- First Error ---")
            sections.append(f"  {first_error}")
            sections.append("")

        return sections
