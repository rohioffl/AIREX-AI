"""Generic investigation plugins for misc Site24x7 monitor types."""

from __future__ import annotations

from airex_core.investigations.base import (
    BaseInvestigation,
    ProbeCategory,
    ProbeResult,
    _make_seeded_rng,
)


def _host(meta: dict) -> str:
    return meta.get("host") or meta.get("monitor_name") or "unknown-target"


def _fmt_ms(value: float) -> str:
    return f"{value:.0f}ms"


def _build_probe(
    tool: str,
    title: str,
    lines: list[str],
    category: ProbeCategory,
    metrics: dict,
) -> ProbeResult:
    body = [f"=== {title} ===", *lines]
    return ProbeResult(
        tool_name=tool,
        raw_output="\n".join(body),
        category=category,
        probe_type="primary",
        metrics=metrics,
    )


class HttpCheckInvestigation(BaseInvestigation):
    alert_type = "http_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        path = incident_meta.get("MONITORURL") or incident_meta.get("url") or "/"
        latency = rng.uniform(650, 1500)
        status = rng.choice([500, 502, 503, 504])
        lines = [
            f"Target URL: https://{host}{path}",
            f"Status: HTTP {status}",
            f"Latency: {_fmt_ms(latency)} (threshold 300ms)",
            "",
            "Recent probe attempts:",
        ]
        attempt_statuses: list[int] = []
        for attempt in range(1, 5):
            attempt_latency = rng.uniform(300, 1400)
            attempt_status = status if attempt in (3, 4) else 200
            attempt_statuses.append(attempt_status)
            lines.append(
                f"  Attempt {attempt}: HTTP {attempt_status} in {_fmt_ms(attempt_latency)}"
            )
        error_count = sum(1 for s in attempt_statuses if s >= 400)
        lines += [
            "",
            "Diagnosis: Origin returning 5xx with elevated latency.",
            "Recommendation: Verify upstream app health and recent deploys.",
        ]
        return _build_probe(
            "synthetic_http_probe",
            f"HTTP Check: {host}",
            lines,
            ProbeCategory.APPLICATION,
            {
                "http_status": status,
                "latency_ms": round(latency, 1),
                "latency_threshold_ms": 300,
                "error_count": error_count,
                "total_attempts": 4,
                "error_rate_percent": round(error_count / 4 * 100, 1),
                "target_url": f"https://{host}{path}",
            },
        )


class ApiCheckInvestigation(BaseInvestigation):
    alert_type = "api_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        endpoint = incident_meta.get("endpoint") or "/health"
        status = rng.choice([401, 429, 500])
        latency = rng.uniform(400, 900)
        method = incident_meta.get("HTTP_METHOD", "GET")
        lines = [
            "Request:",
            f"  {method} {endpoint}",
            "Response:",
            f"  Status: {status}",
            f"  Duration: {_fmt_ms(latency)}",
            "  Body:",
            f"    {incident_meta.get('INCIDENT_REASON', 'Service unavailable')}",
            "",
            "Upstream dependency traces:",
        ]
        dep_statuses: dict[str, int] = {}
        dep_latencies: dict[str, float] = {}
        for dep in ("auth-service", "db", "cache"):
            dep_lat = rng.uniform(20, 120)
            dep_st = rng.choice([200, 200, 500])
            dep_statuses[dep] = dep_st
            dep_latencies[dep] = round(dep_lat, 1)
            lines.append(f"  {dep}: {dep_lat:.1f}ms, status={dep_st}")
        failed_deps = [d for d, s in dep_statuses.items() if s >= 400]
        return _build_probe(
            "api_probe",
            f"API Check: {host}",
            lines,
            ProbeCategory.APPLICATION,
            {
                "http_status": status,
                "latency_ms": round(latency, 1),
                "method": method,
                "endpoint": endpoint,
                "upstream_dependencies": dep_statuses,
                "upstream_latencies": dep_latencies,
                "failed_dependencies": failed_deps,
            },
        )


class CloudCheckInvestigation(BaseInvestigation):
    alert_type = "cloud_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        provider = (
            incident_meta.get("cloud") or incident_meta.get("_cloud") or "aws"
        ).upper()
        resource = (
            incident_meta.get("resource")
            or incident_meta.get("MONITORNAME")
            or "unknown"
        )
        api_error_rate = round(rng.uniform(2, 7), 1)
        throttle_count = rng.randint(200, 600)
        cp_latency = round(rng.uniform(250, 600), 1)
        lines = [
            f"Provider: {provider}",
            f"Resource: {resource}",
            f"Region: {incident_meta.get('_region') or 'auto-detect'}",
            "",
            "Latest health metrics:",
            f"  API error rate: {api_error_rate}% (threshold 1.0%)",
            f"  Throttle count: {throttle_count} in last 5m",
            f"  Control-plane latency: {_fmt_ms(cp_latency)}",
            "",
            "DescribeEvents output:",
            f"  {incident_meta.get('INCIDENT_REASON', 'Control plane returned throttling errors')}",
        ]
        return _build_probe(
            "cloud_api_probe",
            f"Cloud Check: {resource}",
            lines,
            ProbeCategory.INFRASTRUCTURE,
            {
                "provider": provider,
                "resource": resource,
                "api_error_rate_percent": api_error_rate,
                "throttle_count_5m": throttle_count,
                "control_plane_latency_ms": cp_latency,
                "region": incident_meta.get("_region") or "auto-detect",
            },
        )


class DatabaseCheckInvestigation(BaseInvestigation):
    alert_type = "database_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        db = incident_meta.get("MONITORNAME") or "database"
        query_time = rng.uniform(1200, 3500)
        conn_attempts = rng.randint(3, 6)
        conn_failures = 2
        lines = [
            f"Database: {db}",
            "Test query: SELECT 1",
            f"Execution time: {_fmt_ms(query_time)}",
            f"Connection attempts: {conn_attempts} ({conn_failures} failures)",
            "",
            "pg_stat_activity sample:",
        ]
        active_queries = []
        for _ in range(3):
            pid = rng.randint(200, 400)
            dur = rng.uniform(800, 1200)
            active_queries.append({"pid": pid, "duration_ms": round(dur, 1)})
            lines.append(
                f"  pid={pid} state=active duration={_fmt_ms(dur)} query='INSERT ...'"
            )
        lines += [
            "",
            "Diagnosis: Slow response from primary instance.",
            "Recommendation: Investigate long-running transactions and disk saturation.",
        ]
        return _build_probe(
            "db_health_probe",
            f"Database Check: {db}",
            lines,
            ProbeCategory.DATABASE,
            {
                "query_time_ms": round(query_time, 1),
                "connection_attempts": conn_attempts,
                "connection_failures": conn_failures,
                "active_query_count": len(active_queries),
                "max_query_duration_ms": max(q["duration_ms"] for q in active_queries),
                "database_name": db,
            },
        )


class LogAnomalyInvestigation(BaseInvestigation):
    alert_type = "log_anomaly"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        reason = incident_meta.get("INCIDENT_REASON") or "Spike in error logs"
        error_count = rng.randint(50, 300)
        lines = [
            f"Service: {host}",
            f"Detected anomaly: {reason}",
            "",
            "Sample log lines:",
        ]
        for _ in range(3):
            lines.append(
                f"  {rng.randint(12, 23)}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}Z"
                f" ERROR transaction failed: trace_id={rng.randint(10**5, 10**6)}"
            )
        lines += [
            "",
            f"Error volume: {error_count} errors in last 15 minutes",
            "Recommendation: Inspect recent deploy or upstream dependency.",
        ]
        return _build_probe(
            "log_anomaly_scan",
            f"Log Anomaly: {host}",
            lines,
            ProbeCategory.APPLICATION,
            {
                "error_count_15m": error_count,
                "anomaly_reason": reason,
                "service": host,
            },
        )


class PluginCheckInvestigation(BaseInvestigation):
    alert_type = "plugin_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        plugin_name = incident_meta.get("MONITORNAME") or "custom-plugin"
        exit_code = rng.choice([1, 2, 3])
        metric_value = round(rng.uniform(0, 1), 3)
        lines = [
            f"Plugin: {plugin_name}",
            f"Exit code: {exit_code}",
            "Stdout:",
            f"  metric.value={metric_value}",
            "Stderr:",
            f"  {incident_meta.get('INCIDENT_REASON', 'Script reported failure')}",
        ]
        return _build_probe(
            "plugin_runner",
            f"Plugin Check: {plugin_name}",
            lines,
            ProbeCategory.APPLICATION,
            {
                "exit_code": exit_code,
                "metric_value": metric_value,
                "plugin_name": plugin_name,
            },
        )


class HeartbeatCheckInvestigation(BaseInvestigation):
    alert_type = "heartbeat_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        last_heartbeat_min = rng.randint(5, 15)
        expected_freq = incident_meta.get("POLLFREQUENCY", "1")
        lines = [
            f"Host: {host}",
            f"Last heartbeat received: {last_heartbeat_min} minutes ago",
            f"Expected frequency: {expected_freq} minute",
            "",
            "Recent attempts:",
        ]
        timeouts: list[float] = []
        for attempt in range(3):
            t = rng.uniform(800, 1200)
            timeouts.append(t)
            lines.append(f"  Attempt {attempt + 1}: no response (timeout {_fmt_ms(t)})")
        lines.append("Recommendation: verify agent/service on target host.")
        return _build_probe(
            "heartbeat_probe",
            f"Heartbeat Check: {host}",
            lines,
            ProbeCategory.SCHEDULING,
            {
                "last_heartbeat_minutes_ago": last_heartbeat_min,
                "expected_frequency_minutes": int(expected_freq),
                "missed_heartbeats": last_heartbeat_min,
                "consecutive_failures": 3,
                "avg_timeout_ms": round(sum(timeouts) / len(timeouts), 1),
            },
        )


class CronCheckInvestigation(BaseInvestigation):
    alert_type = "cron_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        job = incident_meta.get("MONITORNAME") or "cron-job"
        last_success_hours = rng.randint(2, 4)
        schedule = incident_meta.get("CRON_EXPRESSION", "*/5 * * * *")
        lines = [
            f"Job: {job}",
            f"Schedule: {schedule}",
            f"Last success: {last_success_hours} hours ago",
            "Last failures:",
        ]
        failure_codes: list[int] = []
        for _ in range(2):
            code = rng.choice([1, 2])
            failure_codes.append(code)
            lines.append(
                f"  {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}Z exit code {code}"
            )
        lines.append("Stdout:")
        lines.append("  Traceback... connection timeout to upstream API")
        return _build_probe(
            "cron_probe",
            f"Cron Check: {job}",
            lines,
            ProbeCategory.SCHEDULING,
            {
                "job_name": job,
                "schedule": schedule,
                "last_success_hours_ago": last_success_hours,
                "recent_failure_count": len(failure_codes),
                "last_exit_codes": failure_codes,
            },
        )


class PortCheckInvestigation(BaseInvestigation):
    alert_type = "port_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        port = int(incident_meta.get("PORT", 443))
        lines = [
            f"Target: {host}:{port}",
            "Connection attempts:",
        ]
        timeouts: list[float] = []
        for _ in range(4):
            t = rng.uniform(700, 900)
            timeouts.append(t)
            lines.append(f"  SYN -> timeout after {_fmt_ms(t)}")
        lines.append("Diagnosis: Port unreachable from monitor locations.")
        return _build_probe(
            "tcp_probe",
            f"Port Check: {host}:{port}",
            lines,
            ProbeCategory.NETWORK,
            {
                "target_host": host,
                "port": port,
                "connection_attempts": 4,
                "successful_connections": 0,
                "avg_timeout_ms": round(sum(timeouts) / len(timeouts), 1),
                "port_status": "unreachable",
            },
        )


class SslCheckInvestigation(BaseInvestigation):
    alert_type = "ssl_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        days_left = rng.randint(0, 5)
        ocsp_status = rng.choice(["revoked", "unknown"])
        lines = [
            f"Domain: {host}",
            "Issuer: Let's Encrypt R3",
            f"Expires in: {days_left} days",
            f"OCSP status: {ocsp_status}",
            "",
            "Certificate chain:",
            "  leaf -> intermediate -> ISRG Root X1",
        ]
        lines.append("Recommendation: renew certificate immediately.")
        return _build_probe(
            "ssl_probe",
            f"SSL Check: {host}",
            lines,
            ProbeCategory.SECURITY,
            {
                "domain": host,
                "issuer": "Let's Encrypt R3",
                "days_until_expiry": days_left,
                "ocsp_status": ocsp_status,
                "certificate_expired": days_left <= 0,
                "chain_valid": True,
            },
        )


class MailCheckInvestigation(BaseInvestigation):
    alert_type = "mail_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        latency = round(rng.uniform(500, 900), 1)
        lines = [
            f"SMTP Host: {host}",
            "Handshake log:",
            "  > 220 smtp.example.com ESMTP",
            "  < HELO monitor.site24x7.com",
            "  > 421 App temporarily unable to accept connections",
            f"Round-trip latency: {_fmt_ms(latency)}",
            "",
            "Diagnosis: Mail server returning 421 temporary failure",
        ]
        return _build_probe(
            "smtp_probe",
            f"Mail Check: {host}",
            lines,
            ProbeCategory.SCHEDULING,
            {
                "smtp_host": host,
                "smtp_status": 421,
                "latency_ms": latency,
                "handshake_success": False,
                "error_message": "App temporarily unable to accept connections",
            },
        )


class FtpCheckInvestigation(BaseInvestigation):
    alert_type = "ftp_check"

    async def investigate(self, incident_meta: dict) -> ProbeResult:
        rng = _make_seeded_rng(incident_meta)
        host = _host(incident_meta)
        latency = round(rng.uniform(350, 650), 1)
        lines = [
            f"FTP Host: {host}",
            "Session log:",
            "  > 220 FTP ready",
            "  < USER monitor",
            "  > 331 Password required",
            "  < PASS ******",
            "  > 530 Login incorrect",
            "  < QUIT",
            f"Latency: {_fmt_ms(latency)}",
            "Diagnosis: Authentication failure detected",
        ]
        return _build_probe(
            "ftp_probe",
            f"FTP Check: {host}",
            lines,
            ProbeCategory.SCHEDULING,
            {
                "ftp_host": host,
                "ftp_status": 530,
                "latency_ms": latency,
                "auth_success": False,
                "error_message": "Login incorrect",
            },
        )
