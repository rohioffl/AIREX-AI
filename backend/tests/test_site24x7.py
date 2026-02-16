"""Tests for Site24x7 webhook schema and mapping."""

import pytest

from app.schemas.webhook import Site24x7Payload
from app.api.routes.webhooks import _map_site24x7_alert_type, MONITOR_TYPE_MAP


class TestSite24x7Payload:
    """Verify the flexible Site24x7 payload schema."""

    def test_uppercase_fields(self):
        payload = Site24x7Payload(
            MONITORNAME="Web Server",
            STATUS="DOWN",
            MONITORTYPE="URL",
            MONITORID="123",
        )
        assert payload.get_monitor_name() == "Web Server"
        assert payload.get_status() == "DOWN"
        assert payload.get_monitor_type() == "URL"
        assert payload.get_monitor_id() == "123"

    def test_lowercase_fields(self):
        payload = Site24x7Payload(
            monitor_name="DB Server",
            status="TROUBLE",
            monitor_type="SERVER",
            monitor_id="456",
        )
        assert payload.get_monitor_name() == "DB Server"
        assert payload.get_status() == "TROUBLE"
        assert payload.get_monitor_type() == "SERVER"
        assert payload.get_monitor_id() == "456"

    def test_uppercase_takes_precedence(self):
        payload = Site24x7Payload(
            MONITORNAME="Upper",
            monitor_name="Lower",
            STATUS="DOWN",
            status="TROUBLE",
        )
        assert payload.get_monitor_name() == "Upper"
        assert payload.get_status() == "DOWN"

    def test_empty_payload_defaults(self):
        payload = Site24x7Payload()
        assert payload.get_monitor_name() == "unknown"
        assert payload.get_status() == "unknown"
        assert payload.get_monitor_type() == "unknown"

    def test_extra_fields_allowed(self):
        payload = Site24x7Payload(
            MONITORNAME="Test",
            STATUS="DOWN",
            custom_field="custom_value",
        )
        assert payload.get_monitor_name() == "Test"

    def test_incident_reason(self):
        payload = Site24x7Payload(
            INCIDENT_REASON="Connection refused",
        )
        assert payload.get_incident_reason() == "Connection refused"

    def test_incident_reason_lowercase(self):
        payload = Site24x7Payload(
            incident_reason="Timeout",
        )
        assert payload.get_incident_reason() == "Timeout"


class TestMonitorTypeMapping:
    """Verify monitor type → alert type mapping."""

    def test_url_maps_to_http_check(self):
        assert _map_site24x7_alert_type("URL") == "http_check"

    def test_homepage_maps_to_http_check(self):
        assert _map_site24x7_alert_type("HOMEPAGE") == "http_check"

    def test_server_maps_to_cpu_high(self):
        assert _map_site24x7_alert_type("SERVER") == "cpu_high"

    def test_ping_maps_to_network_issue(self):
        assert _map_site24x7_alert_type("PING") == "network_issue"

    def test_dns_maps_to_network_issue(self):
        assert _map_site24x7_alert_type("DNS") == "network_issue"

    def test_restapi_maps_to_api_check(self):
        assert _map_site24x7_alert_type("RESTAPI") == "api_check"

    def test_ssl_maps_to_ssl_check(self):
        assert _map_site24x7_alert_type("SSL") == "ssl_check"

    def test_unknown_type_passes_through(self):
        result = _map_site24x7_alert_type("CUSTOM MONITOR")
        assert result == "custom_monitor"

    def test_ec2_maps_to_cpu_high(self):
        assert _map_site24x7_alert_type("EC2INSTANCE") == "cpu_high"

    def test_rds_maps_to_database_check(self):
        assert _map_site24x7_alert_type("RDSINSTANCE") == "database_check"

    def test_registry_has_expected_entries(self):
        assert len(MONITOR_TYPE_MAP) >= 15
