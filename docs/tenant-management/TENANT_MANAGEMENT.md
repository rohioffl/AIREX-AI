# Tenant Management — UI & Architecture

> DB-backed tenant CRUD with full credential management in the Admin Panel.

---

## UI Screens

### 1. Tenant List View

The main Tenants tab in Super Admin. Shows all configured tenants with cloud badges, credential status, and quick actions.

![Tenant list with stats, search, cloud badges, credential indicators, and edit/delete](images/tenant_list_view.png)

**Features:**
- **Stats row** — Total tenants, cloud providers, total servers
- **Search/filter** bar
- **Reload Config** — Hot-reloads tenant config from DB
- **Onboard Tenant** — Opens the multi-step wizard
- **Per-tenant cards** showing:
  - Display name + slug (monospace)
  - Cloud badge: **GCP** (green) / **AWS** (orange)
  - Server count
  - Credential status: 🟢 Configured / 🟡 Missing
  - Escalation email
  - Edit ✏️ / Delete 🗑️ buttons

---

### 2. Onboard Wizard — Step 2: Cloud Credentials (AWS)

#### Option A: Cross-Account Role Assumption (Recommended)

![Step 2 wizard with Role Assumption — Account ID, Role Name, External ID](images/wizard_step2_role.png)

Creates an IAM role in the customer's AWS account that trusts AIREX's account. The most secure method.

| Field | Example | Required |
|-------|---------|----------|
| Account ID | `123456789012` | ✅ |
| Role Name | `AirexReadOnly` | ✅ |
| External ID | `airex-trust-xyz` | Optional (but recommended for trust policy) |

**How the trust entity works:**
```json
{
  "Effect": "Allow",
  "Principal": { "AWS": "arn:aws:iam::AIREX_ACCOUNT:root" },
  "Action": "sts:AssumeRole",
  "Condition": { "StringEquals": { "sts:ExternalId": "airex-trust-xyz" } }
}
```

AIREX calls `sts:AssumeRole` at runtime to get temporary credentials.

---

#### Option B: Access Key + Secret Key

![Step 2 wizard with Access Key — masked secret, security warning](images/wizard_step2_keys.png)

Direct IAM user credentials. The simplest method but least secure for production.

| Field | Example | Required |
|-------|---------|----------|
| Access Key ID | `AKIAIOSFODNN7EXAMPLE` | ✅ |
| Secret Access Key | `••••••••••••••••` (masked) | ✅ |

> ⚠️ **Warning**: Keys are stored in the database. Use Role Assumption for production environments.

---

### 3. All Auth Methods

#### AWS (5 methods)

| Method | When to Use | Fields Stored |
|--------|------------|---------------|
| **Cross-Account Role** | Multi-account production | `account_id`, `role_name`, `external_id` |
| **Explicit Role ARN** | When you have the full ARN | `role_arn` |
| **Access Key + Secret Key** | Quick setup / testing | `access_key_id`, `secret_access_key` |
| **Credentials File** | File already on server | `credentials_file` (path) |
| **Instance Role** | AIREX runs on EC2 with IAM role | Nothing (uses instance metadata) |

#### GCP (3 methods)

| Method | When to Use | Fields Stored |
|--------|------------|---------------|
| **Service Account Key File** | Standard SA auth | `project_id`, `service_account_key` (path) |
| **Application Default Credentials** | `gcloud auth` configured | `project_id` only |
| **Automatic** (GCE/GKE) | AIREX runs on GCP | `project_id` only |

---

### 4. Wizard Flow

```
Step 1: Basic Info          Step 2: Credentials        Step 3: SSH          Step 4: Review
┌──────────────────┐       ┌──────────────────┐      ┌───────────────┐    ┌──────────────┐
│ Display Name     │       │ AWS Auth Method  │      │ SSH User      │    │ Summary      │
│ Slug (auto)      │  ──►  │  ◉ Role Assume   │ ──►  │ SSH Port      │ ►  │ Review+Create│
│ Cloud: AWS/GCP   │       │  ○ ARN           │      │ Timeout       │    │ [Create]     │
│ Email            │       │  ○ Access Keys   │      │ Log Lookback  │    │              │
│ Slack Channel    │       │  ○ Creds File    │      │               │    │              │
│                  │       │  ○ Instance Role  │      │               │    │              │
│                  │       │ Region           │      │               │    │              │
└──────────────────┘       └──────────────────┘      └───────────────┘    └──────────────┘
```

---

## Architecture

### Historical (YAML-only, deprecated)

```
tenants.yaml ──► tenant_config.py ──► consumers
                  (cache)              (legacy path — do not use for new deployments)
```

### Current (DB-backed + organizations)

```
┌────────────┐     ┌──────────────────┐     ┌───────────────────────────────────┐
│ Admin UI   │────►│ CRUD API         │────►│ PostgreSQL                        │
│ (React)    │     │ tenants, orgs    │     │ organizations + tenants (+ RLS    │
│ Platform   │     │ platform_admin   │     │  data tables keyed by tenant_id)  │
└────────────┘     └──────────────────┘     └───────┬───────────────────────────┘
                                                     │
                                          ┌──────────┴──────────┐
                                          │ tenant_config.py    │
                                          │ (reads from DB,     │
                                          │  cached)            │
                                          └──────────┬──────────┘
                                                     │
                                          ┌──────────┴──────────┐
                                          │ Worker + plugins    │
                                          │ (investigations,    │
                                          │  actions, cloud)    │
                                          └─────────────────────┘
```

### Database Schema

```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(100) UNIQUE NOT NULL,   -- slug
    display_name    VARCHAR(255) NOT NULL,
    cloud           VARCHAR(10) NOT NULL,           -- 'aws' or 'gcp'
    is_active       BOOLEAN DEFAULT TRUE,

    -- Contacts
    escalation_email VARCHAR(320) DEFAULT '',
    slack_channel    VARCHAR(100) DEFAULT '',

    -- SSH
    ssh_user        VARCHAR(100) DEFAULT 'ubuntu',

    -- Cloud config (JSONB for flexibility)
    aws_config      JSONB DEFAULT '{}',
    gcp_config      JSONB DEFAULT '{}',

    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

**`aws_config` JSONB structure:**
```json
{
  "region": "ap-south-1",
  "account_id": "123456789012",
  "role_name": "AirexReadOnly",
  "role_arn": "",
  "external_id": "airex-trust-xyz",
  "access_key_id": "",
  "secret_access_key": "",
  "credentials_file": "",
  "profile": "",
  "ssm_document": "AWS-RunShellScript",
  "ssm_timeout": 30
}
```

**`gcp_config` JSONB structure:**
```json
{
  "project_id": "my-production-project",
  "service_account_key": "config/credentials/sa.json",
  "zone": "",
  "os_login_user": ""
}
```

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/tenants/` | Authenticated | List tenants visible to the caller (org / membership scoped unless platform admin) |
| `GET` | `/api/v1/tenants/{name}` | Authenticated | Get tenant detail (same visibility rules) |
| `POST` | `/api/v1/tenants/` | Org admin / platform admin | Create tenant (requires **`organization_id`**) |
| `PUT` | `/api/v1/tenants/{name}` | Org admin / platform admin | Update tenant |
| `DELETE` | `/api/v1/tenants/{name}` | Org admin / platform admin | Soft-delete tenant |
| `POST` | `/api/v1/tenants/reload` | Admin | Reload config cache |

### Create Request Body

```json
{
  "organization_id": "11111111-1111-1111-1111-111111111111",
  "name": "acme-corp",
  "display_name": "Acme Corporation",
  "cloud": "aws",
  "escalation_email": "sre@acme.com",
  "slack_channel": "#acme-alerts",
  "ssh_user": "ubuntu",
  "aws_config": {
    "account_id": "123456789012",
    "role_name": "AirexReadOnly",
    "external_id": "airex-trust-xyz",
    "region": "ap-south-1"
  }
}
```

---

## Files Changed

| File | Change |
|------|--------|
| `models/tenant.py` | **NEW** — `Tenant` SQLAlchemy model |
| `models/__init__.py` | Register `Tenant` |
| `alembic/versions/010_add_tenants_table.py` | **NEW** — Migration + YAML seed |
| `cloud/tenant_config.py` | Read from DB instead of YAML |
| `api/routes/tenants.py` | Add POST/PUT/DELETE endpoints |
| `apps/web/src/services/api.js` | Add CRUD functions |
| `apps/web/src/pages/SuperAdminPage.jsx` | Overhaul TenantsTab + Wizard |
