"""Shared test fixtures for the AIREX backend test suite."""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.enums import IncidentState, SeverityLevel, RiskLevel


@pytest.fixture
def tenant_id():
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def incident_id():
    return uuid.uuid4()


@pytest.fixture
def sample_meta():
    return {
        "monitor_name": "web-server-01",
        "status": "DOWN",
        "monitor_type": "URL",
    }


@pytest.fixture
def sample_recommendation():
    return {
        "root_cause": "High CPU usage caused by runaway process",
        "proposed_action": "restart_service",
        "risk_level": "MED",
        "confidence": 0.85,
    }
