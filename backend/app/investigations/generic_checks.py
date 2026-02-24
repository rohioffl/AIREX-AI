"""Generic investigation plugins for misc Site24x7 monitor types."""

from __future__ import annotations

from dataclasses import dataclass

from app.investigations.base import (
    BaseInvestigation,
    InvestigationResult,
    _make_seeded_rng,
)


def _host(meta: dict) -> str:
    return meta.get("host") or meta.get("monitor_name") or "unknown-target"


def _fmt_ms(value: float) -> str:
    return f"{value:.0f}ms"


def _build_result(tool: str, title: str, lines: list[str]) -> InvestigationResult:
    body = [f"=== {title} ===", *lines]
    return InvestigationResult(tool_name=tool, raw_output="\n".join(body))


class HttpCheckInvestigation(BaseInvestigation):
    alert_type = "http_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        path = meta.get("MONITORURL") or meta.get("url") or "/"
        latency = rng.uniform(650, 1500)
        status = rng.choice([500, 502, 503, 504])
        lines = [
            f"Target URL: https://{host}{path}",
            f"Status: HTTP {status}",
            f"Latency: {_fmt_ms(latency)} (threshold 300ms)",
            "",
            "Recent probe attempts:",
        ]
        for attempt in range(1, 5):
            attempt_latency = rng.uniform(300, 1400)
            attempt_status = status if attempt in (3, 4) else 200
            lines.append(
                f"  Attempt {attempt}: HTTP {attempt_status} in {_fmt_ms(attempt_latency)}"
            )
        lines += [
            "",
            "Diagnosis: Origin returning 5xx with elevated latency.",
            "Recommendation: Verify upstream app health and recent deploys.",
        ]
        return _build_result("synthetic_http_probe", f"HTTP Check: {host}", lines)


class ApiCheckInvestigation(BaseInvestigation):
    alert_type = "api_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        endpoint = meta.get("endpoint") or "/health"
        status = rng.choice([401, 429, 500])
        latency = rng.uniform(400, 900)
        payload = {
            "method": meta.get("HTTP_METHOD", "GET"),
            "path": endpoint,
            "status": status,
            "duration_ms": round(latency),
            "response_body": {
                "error": meta.get("INCIDENT_REASON", "Service unavailable"),
            },
        }
        lines = [
            "Request:",
            f"  {payload['method']} {payload['path']}",
            "Response:",
            f"  Status: {status}",
            f"  Duration: {_fmt_ms(latency)}",
            "  Body:",
            f"    {payload['response_body']['error']}",
            "",
            "Upstream dependency traces:",
        ]
        for dep in ("auth-service", "db", "cache"):
            lines.append(
                f"  {dep}: {rng.uniform(20, 120):.1f}ms, status={rng.choice([200, 200, 500])}"
            )
        return _build_result("api_probe", f"API Check: {host}", lines)


class CloudCheckInvestigation(BaseInvestigation):
    alert_type = "cloud_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        provider = (meta.get("cloud") or meta.get("_cloud") or "aws").upper()
        resource = meta.get("resource") or meta.get("MONITORNAME") or "unknown"
        lines = [
            f"Provider: {provider}",
            f"Resource: {resource}",
            f"Region: {meta.get('_region') or 'auto-detect'}",
            "",
            "Latest health metrics:",
            f"  API error rate: {rng.uniform(2, 7):.1f}% (threshold 1.0%)",
            f"  Throttle count: {rng.randint(200, 600)} in last 5m",
            f"  Control-plane latency: {_fmt_ms(rng.uniform(250, 600))}",
            "",
            "DescribeEvents output:",
            f"  {meta.get('INCIDENT_REASON', 'Control plane returned throttling errors')}",
        ]
        return _build_result("cloud_api_probe", f"Cloud Check: {resource}", lines)


class DatabaseCheckInvestigation(BaseInvestigation):
    alert_type = "database_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        db = meta.get("MONITORNAME") or "database"
        query_time = rng.uniform(1200, 3500)
        lines = [
            f"Database: {db}",
            f"Test query: SELECT 1",
            f"Execution time: {_fmt_ms(query_time)}",
            f"Connection attempts: {rng.randint(3, 6)} (2 failures)",
            "",
            "pg_stat_activity sample:",
        ]
        for pid in range(3):
            lines.append(
                f"  pid={rng.randint(200, 400)} state=active duration={_fmt_ms(rng.uniform(800, 1200))} query='INSERT ...'"
            )
        lines += [
            "",
            "Diagnosis: Slow response from primary instance.",
            "Recommendation: Investigate long-running transactions and disk saturation.",
        ]
        return _build_result("db_health_probe", f"Database Check: {db}", lines)


class LogAnomalyInvestigation(BaseInvestigation):
    alert_type = "log_anomaly"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        reason = meta.get("INCIDENT_REASON") or "Spike in error logs"
        lines = [
            f"Service: {host}",
            f"Detected anomaly: {reason}",
            "",
            "Sample log lines:",
        ]
        for _ in range(3):
            lines.append(
                f"  {rng.randint(12, 23)}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}Z ERROR transaction failed: trace_id={rng.randint(10**5, 10**6)}"
            )
        lines += [
            "",
            "Recommendation: Inspect recent deploy or upstream dependency.",
        ]
        return _build_result("log_anomaly_scan", f"Log Anomaly: {host}", lines)


class PluginCheckInvestigation(BaseInvestigation):
    alert_type = "plugin_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        plugin_name = meta.get("MONITORNAME") or "custom-plugin"
        lines = [
            f"Plugin: {plugin_name}",
            f"Exit code: {rng.choice([1, 2, 3])}",
            "Stdout:",
            f"  metric.value={rng.uniform(0, 1):.3f}",
            "Stderr:",
            f"  {meta.get('INCIDENT_REASON', 'Script reported failure')}",
        ]
        return _build_result("plugin_runner", f"Plugin Check: {plugin_name}", lines)


class HeartbeatCheckInvestigation(BaseInvestigation):
    alert_type = "heartbeat_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        last = rng.randint(5, 15)
        lines = [
            f"Host: {host}",
            f"Last heartbeat received: {last} minutes ago",
            f"Expected frequency: {meta.get('POLLFREQUENCY', '1')} minute",
            "",
            "Recent attempts:",
        ]
        for attempt in range(3):
            lines.append(
                f"  Attempt {attempt + 1}: no response (timeout {_fmt_ms(rng.uniform(800, 1200))})"
            )
        lines.append("Recommendation: verify agent/service on target host.")
        return _build_result("heartbeat_probe", f"Heartbeat Check: {host}", lines)


class CronCheckInvestigation(BaseInvestigation):
    alert_type = "cron_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        job = meta.get("MONITORNAME") or "cron-job"
        lines = [
            f"Job: {job}",
            f"Schedule: {meta.get('CRON_EXPRESSION', '*/5 * * * *')}",
            f"Last success: {rng.randint(2, 4)} hours ago",
            "Last failures:",
        ]
        for _ in range(2):
            lines.append(
                f"  {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}Z exit code {rng.choice([1, 2])}"
            )
        lines.append("Stdout:")
        lines.append("  Traceback... connection timeout to upstream API")
        return _build_result("cron_probe", f"Cron Check: {job}", lines)


class PortCheckInvestigation(BaseInvestigation):
    alert_type = "port_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        port = int(meta.get("PORT", 443))
        lines = [
            f"Target: {host}:{port}",
            "Connection attempts:",
        ]
        for _ in range(4):
            lines.append(f"  SYN -> timeout after {_fmt_ms(rng.uniform(700, 900))}")
        lines.append("Diagnosis: Port unreachable from monitor locations.")
        return _build_result("tcp_probe", f"Port Check: {host}:{port}", lines)


class SslCheckInvestigation(BaseInvestigation):
    alert_type = "ssl_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        days_left = rng.randint(0, 5)
        lines = [
            f"Domain: {host}",
            f"Issuer: Let's Encrypt R3",
            f"Expires in: {days_left} days",
            f"OCSP status: {rng.choice(['revoked', 'unknown'])}",
            "",
            "Certificate chain:",
            "  leaf -> intermediate -> ISRG Root X1",
        ]
        lines.append("Recommendation: renew certificate immediately.")
        return _build_result("ssl_probe", f"SSL Check: {host}", lines)


class MailCheckInvestigation(BaseInvestigation):
    alert_type = "mail_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        lines = [
            f"SMTP Host: {host}",
            "Handshake log:",
            "  > 220 smtp.example.com ESMTP",
            "  < HELO monitor.site24x7.com",
            "  > 421 App temporarily unable to accept connections",
            f"Round-trip latency: {_fmt_ms(rng.uniform(500, 900))}",
            "",
            "Diagnosis: Mail server returning 421 temporary failure",
        ]
        return _build_result("smtp_probe", f"Mail Check: {host}", lines)


class FtpCheckInvestigation(BaseInvestigation):
    alert_type = "ftp_check"

    async def investigate(self, meta: dict) -> InvestigationResult:
        rng = _make_seeded_rng(meta)
        host = _host(meta)
        lines = [
            f"FTP Host: {host}",
            "Session log:",
            "  > 220 FTP ready",
            "  < USER monitor",
            "  > 331 Password required",
            "  < PASS ******",
            "  > 530 Login incorrect",
            "  < QUIT",
            f"Latency: {_fmt_ms(rng.uniform(350, 650))}",
            "Diagnosis: Authentication failure detected",
        ]
        return _build_result("ftp_probe", f"FTP Check: {host}", lines)
