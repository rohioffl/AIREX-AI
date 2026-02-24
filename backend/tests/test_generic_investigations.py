import pytest

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "plugin_cls",
    [
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
    ],
)
async def test_generic_investigations_produce_evidence(plugin_cls):
    plugin = plugin_cls()
    meta = {
        "monitor_name": "unit-test-host",
        "INCIDENT_REASON": "Simulated outage",
    }

    result = await plugin.investigate(meta)

    assert result.tool_name
    assert isinstance(result.raw_output, str)
    assert len(result.raw_output.strip()) > 0
