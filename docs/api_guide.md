# AIREX API Guide

Base URL: `http://localhost:8000/api/v1`

## Authentication

### Register
```http
POST /auth/register
Content-Type: application/json

{
  "email": "operator@example.com",
  "password": "SecurePass123!",
  "display_name": "Alex Operator",
  "tenant_id": "00000000-0000-0000-0000-000000000000"  // optional
}
```

**Response** `201 Created`
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "email": "operator@example.com",
  "display_name": "Alex Operator",
  "role": "operator"
}
```

### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "operator@example.com",
  "password": "SecurePass123!"
}
```

**Response** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 691200
}
```

### Refresh Token
```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

## Webhook Ingestion

### Site24x7 Webhook
```http
POST /webhooks/site24x7
Authorization: Bearer <token>
Content-Type: application/json

{
  "monitor_name": "Production Web Server",
  "monitor_id": "123456",
  "monitor_type": "URL",
  "status": "DOWN",
  "outage_reason": "Connection timeout after 30s"
}
```

**Response** `202 Accepted`
```json
{
  "incident_id": "uuid"
}
```

### Generic Webhook
```http
POST /webhooks/generic
Authorization: Bearer <token>
Content-Type: application/json

{
  "alert_type": "cpu_high",
  "severity": "critical",
  "title": "High CPU on prod-web-01",
  "resource_id": "prod-web-01",
  "meta": {
    "host": "prod-web-01",
    "cpu_percent": 95,
    "service_name": "nginx"
  }
}
```

## Incidents

### List Incidents
```http
GET /incidents?state=INVESTIGATING&severity=CRITICAL&limit=50&offset=0
Authorization: Bearer <token>
```

### Get Incident Detail
```http
GET /incidents/{incident_id}
Authorization: Bearer <token>
```

### Approve Incident
```http
POST /incidents/{incident_id}/approve
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "restart_service",
  "idempotency_key": "unique-key-123"
}
```

**Available Actions:**
- `restart_service` — Restart a system service via SSM
- `clear_logs` — Clear old log files to free disk
- `scale_instances` — Scale up/down instances in ASG

## Server-Sent Events (SSE)

### Subscribe to Events
```http
GET /events/stream?token=<jwt>&x_tenant_id=<uuid>
Accept: text/event-stream
```

**Event Types:**
| Event | Payload |
|-------|---------|
| `incident_created` | `{incident_id, title, state, severity}` |
| `state_changed` | `{incident_id, old_state, new_state, reason}` |
| `evidence_added` | `{incident_id, tool_name, raw_output}` |
| `recommendation_ready` | `{incident_id, action, risk_level}` |
| `execution_started` | `{incident_id, action_type}` |
| `execution_log` | `{incident_id, line}` |
| `execution_completed` | `{incident_id, success, logs}` |
| `verification_result` | `{incident_id, passed}` |
| `heartbeat` | `""` |

## Health & Metrics

```http
GET /health
# {"status": "ok", "service": "airex-backend"}

GET /metrics
# Prometheus exposition format
```

## Rate Limits
| Endpoint Group | Limit | Window |
|---------------|-------|--------|
| `/webhooks/*` | 30 req | 60s |
| `/incidents/*/approve` | 10 req | 60s |
| `/auth/*` | 5 req | 60s |

## Error Codes
| Code | Meaning |
|------|---------|
| 400 | Invalid request payload |
| 401 | Invalid or expired token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (duplicate email, etc.) |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
