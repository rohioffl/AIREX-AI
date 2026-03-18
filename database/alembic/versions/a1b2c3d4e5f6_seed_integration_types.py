"""seed_integration_types

Inserts the canonical catalog of monitoring integration types.
Uses ON CONFLICT DO UPDATE so this migration is safe to re-apply.

Revision ID: a1b2c3d4e5f6
Revises: 9a2b3c4d5e6f
Create Date: 2026-03-17
"""

from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TYPES = [
    {
        "key": "site24x7",
        "display_name": "Site24x7",
        "category": "monitoring",
        "supports_webhook": True,
        "supports_polling": True,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["api_key"],
            "properties": {
                "api_key": {"type": "string", "title": "API Key", "secret": True},
                "monitor_group_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Monitor Group IDs",
                    "default": [],
                },
            },
        },
    },
    {
        "key": "prometheus",
        "display_name": "Prometheus",
        "category": "monitoring",
        "supports_webhook": True,
        "supports_polling": True,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["base_url"],
            "properties": {
                "base_url": {"type": "string", "title": "Prometheus Base URL"},
                "username": {"type": "string", "title": "Basic Auth Username"},
                "password": {"type": "string", "title": "Basic Auth Password", "secret": True},
                "bearer_token": {"type": "string", "title": "Bearer Token", "secret": True},
            },
        },
    },
    {
        "key": "grafana",
        "display_name": "Grafana",
        "category": "observability",
        "supports_webhook": True,
        "supports_polling": False,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["base_url", "api_key"],
            "properties": {
                "base_url": {"type": "string", "title": "Grafana Base URL"},
                "api_key": {"type": "string", "title": "Service Account Token", "secret": True},
                "org_id": {"type": "integer", "title": "Grafana Org ID", "default": 1},
            },
        },
    },
    {
        "key": "datadog",
        "display_name": "Datadog",
        "category": "monitoring",
        "supports_webhook": True,
        "supports_polling": True,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["api_key", "app_key"],
            "properties": {
                "api_key": {"type": "string", "title": "API Key", "secret": True},
                "app_key": {"type": "string", "title": "Application Key", "secret": True},
                "site": {
                    "type": "string",
                    "title": "Datadog Site",
                    "default": "datadoghq.com",
                    "enum": ["datadoghq.com", "datadoghq.eu", "us3.datadoghq.com", "us5.datadoghq.com"],
                },
            },
        },
    },
    {
        "key": "pagerduty",
        "display_name": "PagerDuty",
        "category": "alerting",
        "supports_webhook": True,
        "supports_polling": True,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["api_token"],
            "properties": {
                "api_token": {"type": "string", "title": "REST API Token", "secret": True},
                "service_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Service IDs to watch",
                    "default": [],
                },
            },
        },
    },
    {
        "key": "cloudwatch",
        "display_name": "AWS CloudWatch",
        "category": "monitoring",
        "supports_webhook": False,
        "supports_polling": True,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["aws_region"],
            "properties": {
                "aws_region": {"type": "string", "title": "AWS Region", "default": "us-east-1"},
                "role_arn": {"type": "string", "title": "IAM Role ARN (cross-account)"},
                "aws_access_key_id": {"type": "string", "title": "AWS Access Key ID", "secret": True},
                "aws_secret_access_key": {"type": "string", "title": "AWS Secret Access Key", "secret": True},
            },
        },
    },
    {
        "key": "gcp_monitoring",
        "display_name": "GCP Cloud Monitoring",
        "category": "monitoring",
        "supports_webhook": True,
        "supports_polling": True,
        "supports_sync": True,
        "config_schema_json": {
            "type": "object",
            "required": ["project_id"],
            "properties": {
                "project_id": {"type": "string", "title": "GCP Project ID"},
                "service_account_json": {
                    "type": "string",
                    "title": "Service Account JSON",
                    "secret": True,
                    "description": "Full JSON key file content",
                },
            },
        },
    },
    {
        "key": "uptime_kuma",
        "display_name": "Uptime Kuma",
        "category": "monitoring",
        "supports_webhook": True,
        "supports_polling": False,
        "supports_sync": False,
        "config_schema_json": {
            "type": "object",
            "properties": {
                "webhook_secret": {
                    "type": "string",
                    "title": "Webhook Secret",
                    "secret": True,
                    "description": "Optional secret to validate incoming webhooks",
                },
            },
        },
    },
    {
        "key": "custom_webhook",
        "display_name": "Custom Webhook",
        "category": "custom",
        "supports_webhook": True,
        "supports_polling": False,
        "supports_sync": False,
        "config_schema_json": {
            "type": "object",
            "properties": {
                "hmac_secret": {
                    "type": "string",
                    "title": "HMAC Secret",
                    "secret": True,
                    "description": "Secret used to verify X-Signature header",
                },
                "payload_format": {
                    "type": "string",
                    "title": "Payload Format",
                    "default": "json",
                    "enum": ["json", "form"],
                },
            },
        },
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for entry in _TYPES:
        conn.execute(
            sa.text("""
                INSERT INTO integration_types
                    (id, key, display_name, category,
                     supports_webhook, supports_polling, supports_sync,
                     enabled, config_schema_json)
                VALUES
                    (gen_random_uuid(), :key, :display_name, :category,
                     :supports_webhook, :supports_polling, :supports_sync,
                     TRUE, CAST(:config_schema_json AS jsonb))
                ON CONFLICT (key) DO UPDATE SET
                    display_name       = EXCLUDED.display_name,
                    category           = EXCLUDED.category,
                    supports_webhook   = EXCLUDED.supports_webhook,
                    supports_polling   = EXCLUDED.supports_polling,
                    supports_sync      = EXCLUDED.supports_sync,
                    config_schema_json = EXCLUDED.config_schema_json,
                    updated_at         = CURRENT_TIMESTAMP
            """),
            {
                "key": entry["key"],
                "display_name": entry["display_name"],
                "category": entry["category"],
                "supports_webhook": entry["supports_webhook"],
                "supports_polling": entry["supports_polling"],
                "supports_sync": entry["supports_sync"],
                "config_schema_json": json.dumps(entry["config_schema_json"]),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [e["key"] for e in _TYPES]
    conn.execute(
        sa.text("DELETE FROM integration_types WHERE key = ANY(CAST(:keys AS text[]))"),
        {"keys": keys},
    )
