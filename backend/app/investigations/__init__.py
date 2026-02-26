from app.investigations.base import BaseInvestigation, InvestigationResult, ProbeResult
from app.investigations.cpu_high import CpuHighInvestigation
from app.investigations.disk_full import DiskFullInvestigation
from app.investigations.memory_high import MemoryHighInvestigation
from app.investigations.network_check import NetworkCheckInvestigation
from app.investigations.healthcheck import HealthCheckInvestigation
from app.investigations.generic_checks import (
    HttpCheckInvestigation,
    ApiCheckInvestigation,
    CloudCheckInvestigation,
    DatabaseCheckInvestigation,
    LogAnomalyInvestigation,
    PluginCheckInvestigation,
    HeartbeatCheckInvestigation,
    CronCheckInvestigation,
    PortCheckInvestigation,
    SslCheckInvestigation,
    MailCheckInvestigation,
    FtpCheckInvestigation,
)

INVESTIGATION_REGISTRY: dict[str, type[BaseInvestigation]] = {
    "cpu_high": CpuHighInvestigation,
    "disk_full": DiskFullInvestigation,
    "memory_high": MemoryHighInvestigation,
    "network_issue": NetworkCheckInvestigation,
    "healthcheck": HealthCheckInvestigation,
    "http_check": HttpCheckInvestigation,
    "api_check": ApiCheckInvestigation,
    "cloud_check": CloudCheckInvestigation,
    "database_check": DatabaseCheckInvestigation,
    "log_anomaly": LogAnomalyInvestigation,
    "plugin_check": PluginCheckInvestigation,
    "heartbeat_check": HeartbeatCheckInvestigation,
    "cron_check": CronCheckInvestigation,
    "port_check": PortCheckInvestigation,
    "ssl_check": SslCheckInvestigation,
    "mail_check": MailCheckInvestigation,
    "ftp_check": FtpCheckInvestigation,
}

__all__ = [
    "BaseInvestigation",
    "InvestigationResult",
    "ProbeResult",
    "INVESTIGATION_REGISTRY",
]
