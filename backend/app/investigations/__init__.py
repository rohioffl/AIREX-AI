from app.investigations.base import BaseInvestigation
from app.investigations.cpu_high import CpuHighInvestigation
from app.investigations.disk_full import DiskFullInvestigation
from app.investigations.memory_high import MemoryHighInvestigation
from app.investigations.network_check import NetworkCheckInvestigation

INVESTIGATION_REGISTRY: dict[str, type[BaseInvestigation]] = {
    "cpu_high": CpuHighInvestigation,
    "disk_full": DiskFullInvestigation,
    "memory_high": MemoryHighInvestigation,
    "network_issue": NetworkCheckInvestigation,
}

__all__ = [
    "BaseInvestigation",
    "INVESTIGATION_REGISTRY",
]
