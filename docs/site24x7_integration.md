# Site24x7 Integration Guide

Connect Site24x7 monitoring to AIREX for automated incident investigation and resolution.

## Prerequisites

- AIREX backend running and publicly accessible
- Site24x7 account with admin or super admin access

## Your Webhook URL

```
https://airex.ankercloud.com/api/v1/webhooks/site24x7
```

---

## Step-by-Step: Configure Site24x7

### 1. Create a Webhook Integration

1. Log in to **Site24x7** → go to **Admin** → **Third-Party Integrations**
2. Click **+ Add Third Party Integration** → select **Webhooks**
3. Fill in:

| Field | Value |
|-------|-------|
| **Integration Name** | `AIREX Incident Engine` |
| **Hook URL** | `https://airex.ankercloud.com/api/v1/webhooks/site24x7` |
| **HTTP Method** | `POST` |
| **Content Type** | `application/json` |
| **Send Incident Parameters** | `JSON` |

### 2. Add Custom Headers

Click **+ Add Header** and add:

| Header | Value |
|--------|-------|
| `X-Tenant-Id` | `00000000-0000-0000-0000-000000000000` |
| `Content-Type` | `application/json` |

> Replace the tenant ID with your actual tenant UUID if using multi-tenancy.

### 3. Select JSON Payload Format

Under **Payload**, select **JSON** and use Site24x7's default template. The built-in fields map automatically:

```json
{
  "MONITORNAME": "$MONITORNAME",
  "STATUS": "$STATUS",
  "MONITORTYPE": "$MONITORTYPE",
  "MONITORID": "$MONITORID",
  "INCIDENT_REASON": "$INCIDENT_REASON",
  "INCIDENT_TIME": "$INCIDENT_TIME",
  "INCIDENT_TIME_ISO": "$INCIDENT_TIME_ISO",
  "FAILED_LOCATIONS": "$FAILED_LOCATIONS",
  "MONITOR_DASHBOARD_LINK": "$MONITOR_DASHBOARD_LINK",
  "MONITOR_GROUPNAME": "$MONITOR_GROUPNAME",
  "RCA_LINK": "$RCA_LINK",
  "OUTAGE_DURATION": "$OUTAGE_DURATION",
  "TAGS": "$TAGS"
}
```

### 4. Select Monitors

Choose which monitors should trigger AIREX incidents:
- **All Monitors** — or —
- **Specific monitors/groups** (recommended for initial setup)

### 5. Test & Save

Click **Test** to send a sample payload, then **Save**.

---

## Cloud-Aware Investigation (Tags)

AIREX parses Site24x7 **monitor tags** to determine the cloud provider and target server, then uses **AWS SSM** or **GCP OS Login** to run real diagnostics.

### Required Tags Format

Add these tags to your Site24x7 monitors:

**For GCP instances:**
```
cloud:gcp,tenant:<tenant-name>,ip:<private-ip>,instance:<gce-instance-name>,project:<gcp-project-id>,zone:<gce-zone>
```

Example:
```
cloud:gcp,tenant:acme-corp,ip:10.128.0.15,instance:vm-prod-web-01,project:acme-production,zone:asia-south1-a
```

**For AWS instances:**
```
cloud:aws,tenant:<tenant-name>,ip:<private-ip>,instance:<ec2-instance-id>,region:<aws-region>
```

Example:
```
cloud:aws,tenant:beta-inc,ip:172.31.5.42,instance:i-0abc123def456,region:ap-south-1
```

### Supported Tag Keys

| Tag Key | Description | Example |
|---------|-------------|---------|
| `cloud` | Cloud provider | `gcp`, `aws` |
| `tenant` | Tenant/org name | `acme-corp` |
| `ip` / `private_ip` | Private IP of the server | `10.128.0.15` |
| `instance` / `instance_id` | Instance name or ID | `vm-prod-01`, `i-0abc123` |
| `project` / `project_id` | GCP project ID | `my-gcp-project` |
| `zone` | GCE zone | `asia-south1-a` |
| `region` | AWS region | `ap-south-1` |
| `sa` / `service_account` | GCP service account | `sa@project.iam.gserviceaccount.com` |
| `env` / `environment` | Environment | `prod`, `staging` |

### How Investigation Routes

```
Site24x7 webhook with tags
    ↓
Parse tags → CloudContext
    ↓
┌─ cloud:gcp + has IP/instance ──→ GCP OS Login SSH → run diagnostics
│                                   + GCP Log Explorer → query logs
│
├─ cloud:aws + has instance-id ──→ AWS SSM RunCommand → run diagnostics
│                                   + CloudWatch Logs → query logs
│
└─ no cloud tags ────────────────→ Simulated investigation (fallback)
```

### AWS Prerequisites

1. **AIREX server** needs an IAM role with:
   - `ssm:SendCommand`
   - `ssm:GetCommandInvocation`
   - `logs:FilterLogEvents` (for CloudWatch)

2. **Target EC2 instances** need:
   - SSM Agent installed and running
   - IAM role with `AmazonSSMManagedInstanceCore` policy
   - No SSH keys needed — everything uses IAM roles

### GCP Prerequisites

1. **AIREX server** needs a service account with:
   - `roles/compute.osLogin` (to SSH via OS Login)
   - `roles/logging.viewer` (for Log Explorer)
   - `roles/compute.viewer` (to resolve instance IPs)

2. **Target GCE instances** need:
   - OS Login enabled: metadata `enable-oslogin = TRUE`
   - Service account attached (standard for GCE)
   - No manual SSH key management — Google handles it

### What Diagnostics Run

When AIREX SSHes/SSMs into a server, it runs **read-only** diagnostic commands:

| Alert Type | Commands Run |
|-----------|-------------|
| `cpu_high` | `vmstat`, `ps aux --sort=-%cpu`, `cat /proc/loadavg`, `dmesg` throttling |
| `memory_high` | `free -h`, `ps aux --sort=-%mem`, OOM killer events, swap stats |
| `disk_full` | `df -h`, `du -sh`, largest files, `iostat`, disk errors |
| `network_issue` | `ip addr`, `ss -tuln`, `nslookup`, connection counts, firewall events |
| `http_check` | Network diagnostics + systemd failed units + Docker status |

---

## How It Works

### Monitor Type Mapping

Site24x7 monitor types are automatically mapped to AIREX alert types:

| Site24x7 Monitor Type | AIREX Alert Type | Investigation Plugin |
|----------------------|------------------|---------------------|
| URL / Homepage / RealBrowser | `http_check` | HTTP connectivity |
| REST API | `api_check` | API health |
| Server / Agent Server | `cpu_high` | CPU diagnostics |
| EC2 Instance | `cpu_high` | CPU diagnostics |
| RDS Instance | `database_check` | DB health |
| Ping | `network_issue` | Network check |
| DNS | `network_issue` | Network check |
| SSL Certificate | `ssl_check` | SSL validation |
| Application Log | `log_anomaly` | Log analysis |
| Heartbeat | `heartbeat_check` | Service heartbeat |
| Port | `port_check` | Port connectivity |

### Severity Mapping

| Site24x7 Status | AIREX Severity |
|-----------------|---------------|
| DOWN | CRITICAL |
| CRITICAL | CRITICAL |
| TROUBLE | HIGH |
| UP | *(auto-resolves incident)* |

### Auto-Resolution

When Site24x7 sends an **UP** status webhook, AIREX automatically:
1. Finds the most recent active incident for that tenant
2. Transitions it to `RESOLVED` state
3. Logs the resolution with the recovery time

### Deduplication

AIREX deduplicates alerts using a 5-minute sliding window:
- Same `alert_type` + `monitor_id` within 5 minutes = deduplicated
- Prevents alert storms from creating duplicate incidents

---

## Incident Lifecycle

```
Site24x7 DOWN alert
    ↓
AIREX receives webhook → creates Incident (INVESTIGATING)
    ↓
Investigation plugin runs diagnostics (60s timeout)
    ↓
AI generates recommendation
    ↓
Operator approves in AIREX dashboard
    ↓
Deterministic action executes
    ↓
Verification confirms fix
    ↓
RESOLVED (or ESCALATED if auto-fix fails)
```

---

## Verifying the Connection

### From AIREX Side

Check recent incidents:
```bash
curl -s https://airex.ankercloud.com/api/v1/incidents/ \
  -H "X-Tenant-Id: 00000000-0000-0000-0000-000000000000" | python3 -m json.tool
```

### From Site24x7 Side

1. Go to **Admin** → **Third-Party Integrations**
2. Click on your **AIREX** integration
3. Check **Integration Logs** for delivery status

### Test Webhook Manually

```bash
curl -X POST https://airex.ankercloud.com/api/v1/webhooks/site24x7 \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: 00000000-0000-0000-0000-000000000000" \
  -d '{
    "MONITORNAME": "Test Monitor",
    "STATUS": "DOWN",
    "MONITORTYPE": "URL",
    "MONITORID": "test-001",
    "INCIDENT_REASON": "Connection timeout"
  }'
```

Expected response:
```json
{"incident_id": "uuid-here"}
```

---

## Webhook Signature Verification (Optional)

For added security, set `WEBHOOK_SECRET` in your `.env`:
```
WEBHOOK_SECRET=your-shared-secret-here
```

Then configure Site24x7 to include the secret in the `X-Webhook-Signature` header.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 422 Validation Error | Check JSON payload format matches expected fields |
| 429 Too Many Requests | Rate limit hit (30 webhooks/60s). Wait and retry. |
| Connection refused | Ensure AIREX backend is running and port 8000 is open |
| No incident created | Check for deduplication (same alert within 5 min window) |
| Incident not auto-resolving | Ensure UP webhook includes matching MONITORID |
