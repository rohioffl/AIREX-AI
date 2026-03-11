import pytest

from airex_core.investigations.healthcheck import HealthCheckInvestigation


@pytest.mark.asyncio
async def test_healthcheck_routes_to_cpu_plugin():
    plugin = HealthCheckInvestigation()
    meta = {
        "monitor_name": "prod-api",
        "INCIDENT_REASON": "CPU usage exceeds 95% across all cores",
        "TAGS": ["env:prod", "role:web"],
    }

    result = await plugin.investigate(meta)

    assert result.tool_name == "cpu_diagnostics"
    assert "CPU Investigation" in result.raw_output


@pytest.mark.asyncio
async def test_healthcheck_fallback_probe_runs():
    plugin = HealthCheckInvestigation()
    meta = {
        "monitor_name": "edge-proxy",
        "INCIDENT_REASON": "Healthcheck endpoint returned HTTP 503",
    }

    result = await plugin.investigate(meta)

    assert result.tool_name == "healthcheck_probe"
    assert "Synthetic Health Check" in result.raw_output
