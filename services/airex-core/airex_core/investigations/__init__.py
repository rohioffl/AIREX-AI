from airex_core.investigations.base import BaseInvestigation, InvestigationResult, ProbeResult
from airex_core.investigations.cpu_high import CpuHighInvestigation
from airex_core.investigations.disk_full import DiskFullInvestigation
from airex_core.investigations.memory_high import MemoryHighInvestigation
from airex_core.investigations.network_check import NetworkCheckInvestigation
from airex_core.investigations.healthcheck import HealthCheckInvestigation
from airex_core.investigations.service_down import ServiceDownInvestigation
from airex_core.investigations.generic_checks import (
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
    "service_down": ServiceDownInvestigation,
    "server_check": ServiceDownInvestigation,
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
