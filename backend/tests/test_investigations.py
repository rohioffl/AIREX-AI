"""Tests for investigation plugins."""

import pytest

from app.investigations import INVESTIGATION_REGISTRY
from app.investigations.base import BaseInvestigation, InvestigationResult
from app.investigations.cpu_high import CpuHighInvestigation
from app.investigations.disk_full import DiskFullInvestigation
from app.investigations.memory_high import MemoryHighInvestigation
from app.investigations.network_check import NetworkCheckInvestigation


class TestInvestigationRegistry:
    def test_registry_has_cpu_high(self):
        assert "cpu_high" in INVESTIGATION_REGISTRY

    def test_registry_has_disk_full(self):
        assert "disk_full" in INVESTIGATION_REGISTRY

    def test_registry_has_memory_high(self):
        assert "memory_high" in INVESTIGATION_REGISTRY

    def test_registry_has_network_issue(self):
        assert "network_issue" in INVESTIGATION_REGISTRY

    def test_registry_size(self):
        assert len(INVESTIGATION_REGISTRY) == 4

    def test_registry_values_are_subclasses(self):
        for name, cls in INVESTIGATION_REGISTRY.items():
            assert issubclass(cls, BaseInvestigation)


class TestCpuHighInvestigation:
    @pytest.mark.asyncio
    async def test_investigate_returns_result(self):
        plugin = CpuHighInvestigation()
        result = await plugin.investigate({"monitor_name": "web-01"})
        assert isinstance(result, InvestigationResult)
        assert result.tool_name == "cpu_diagnostics"
        assert "web-01" in result.raw_output

    @pytest.mark.asyncio
    async def test_investigate_with_empty_meta(self):
        plugin = CpuHighInvestigation()
        result = await plugin.investigate({})
        assert isinstance(result, InvestigationResult)
        assert "unknown" in result.raw_output


class TestDiskFullInvestigation:
    @pytest.mark.asyncio
    async def test_investigate_returns_result(self):
        plugin = DiskFullInvestigation()
        result = await plugin.investigate({"monitor_name": "db-01"})
        assert isinstance(result, InvestigationResult)
        assert result.tool_name == "disk_diagnostics"
        assert "db-01" in result.raw_output


class TestMemoryHighInvestigation:
    @pytest.mark.asyncio
    async def test_investigate_returns_result(self):
        plugin = MemoryHighInvestigation()
        result = await plugin.investigate({"monitor_name": "app-server-01"})
        assert isinstance(result, InvestigationResult)
        assert result.tool_name == "memory_diagnostics"
        assert "app-server-01" in result.raw_output


class TestNetworkCheckInvestigation:
    @pytest.mark.asyncio
    async def test_investigate_returns_result(self):
        plugin = NetworkCheckInvestigation()
        result = await plugin.investigate({"monitor_name": "edge-01", "target_host": "api.example.com"})
        assert isinstance(result, InvestigationResult)
        assert result.tool_name == "network_diagnostics"
        assert "edge-01" in result.raw_output
