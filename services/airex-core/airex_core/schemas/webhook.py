from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Site24x7Payload(BaseModel):
    """
    Incoming Site24x7 webhook payload.

    Site24x7 sends these fields in their IT Automation / Webhook Integration.
    The `extra="allow"` config captures any additional custom fields.

    Ref: Site24x7 → Admin → IT Automation → Webhooks
    """

    model_config = ConfigDict(extra="allow")

    # Core fields (always present)
    MONITORNAME: str | None = Field(None, alias="MONITORNAME")
    MONITOR_DASHBOARD_LINK: str | None = None
    MONITORTYPE: str | None = None
    MONITORID: Any | None = None
    MONITOR_ID: Any | None = None
    MONITORURL: str | None = None
    DISPLAYNAME: str | None = None
    STATUS: str | None = None
    INCIDENT_REASON: str | None = None
    INCIDENT_TIME: str | None = None
    INCIDENT_TIME_ISO: str | None = None
    RCA_LINK: str | None = None

    # Location / Group fields
    FAILED_LOCATIONS: str | None = None
    MONITOR_GROUPNAME: str | None = None
    MSP: str | None = None

    # Duration / resolution
    OUTAGE_DURATION: str | None = None
    OUTAGE_START_TIME: str | None = None
    OUTAGE_END_TIME: str | None = None
    RESOLVED_TIME: str | None = None

    # Tags & custom — Site24x7 sends TAGS as either a string or a list
    TAGS: Any | None = None
    MONITOR_TAGS: Any | None = None
    GROUP_TAGS: Any | None = None

    # Server monitor fields (IP / hostname sent by default)
    IPADDRESS: str | None = None
    IP_ADDRESS: str | None = None

    # Legacy lowercase fields (some Site24x7 integrations use these)
    monitor_name: str | None = None
    status: str | None = None
    monitor_type: str | None = None
    incident_reason: str | None = None
    failed_locations: str | None = None
    monitor_id: str | None = None
    monitor_dashboard_link: str | None = None
    ipaddress: str | None = None
    ip_address: str | None = None
    monitorurl: str | None = None
    displayname: str | None = None

    def get_monitor_name(self) -> str:
        return self.MONITORNAME or self.monitor_name or "unknown"

    def get_status(self) -> str:
        return self.STATUS or self.status or "unknown"

    def get_monitor_type(self) -> str:
        return self.MONITORTYPE or self.monitor_type or "unknown"

    def get_monitor_id(self) -> str:
        """Return a usable monitor ID, skipping unresolved Site24x7 template vars."""
        extra = self.model_extra or {}
        for candidate in [
            self.MONITORID,
            self.MONITOR_ID,
            self.monitor_id,
            extra.get("MONITOR_ID"),
            extra.get("monitor_id"),
        ]:
            if candidate is not None:
                val = str(candidate).strip()
                # Reject unresolved template variables like $MONITORID
                if val and not val.startswith("$"):
                    return val
        return self.get_monitor_name()

    def get_incident_reason(self) -> str | None:
        return self.INCIDENT_REASON or self.incident_reason

    def get_ip_address(self) -> str:
        """
        Extract IP from all possible payload fields.

        Site24x7 sends the server IP in various fields depending on
        monitor type: IPADDRESS, IP_ADDRESS, MONITORURL, DISPLAYNAME,
        or even inside MONITORNAME.
        """
        import re

        ip_re = re.compile(
            r"(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r"|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        )

        # Check explicit IP fields first
        for val in [
            self.IPADDRESS,
            self.IP_ADDRESS,
            self.ipaddress,
            self.ip_address,
        ]:
            if val and val.strip():
                return val.strip()

        # Try to extract IP from URL/name fields
        for val in [
            self.MONITORURL,
            self.monitorurl,
            self.DISPLAYNAME,
            self.displayname,
            self.MONITORNAME,
            self.monitor_name,
        ]:
            if val:
                match = ip_re.search(val)
                if match:
                    return match.group(1)

        # Check extra fields (model_config extra="allow")
        extra = self.model_extra or {}
        for key in [
            "ip",
            "ipaddress",
            "ip_address",
            "server_ip",
            "host_ip",
            "IPADDRESS",
            "IP_ADDRESS",
            "SERVER_IP",
            "HOST_IP",
        ]:
            if key in extra and extra[key]:
                return str(extra[key]).strip()

        return ""


class GenericWebhookPayload(BaseModel):
    """Source-agnostic webhook payload for other integrations."""

    model_config = ConfigDict(extra="allow")

    alert_type: str
    resource_id: str
    title: str
    severity: str = "MEDIUM"
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("alert_type", "resource_id", "title", "severity", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
