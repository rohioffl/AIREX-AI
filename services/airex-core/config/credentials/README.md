# Credentials Directory

Store cloud provider credentials here. **Never commit these to git.**

## GCP Service Account Keys

1. Go to GCP Console → IAM → Service Accounts
2. Create or select a service account with these roles:
   - `roles/compute.osLogin` (SSH via OS Login)
   - `roles/compute.viewer` (auto-discover instances by IP)
   - `roles/logging.viewer` (query Log Explorer)
3. Create a JSON key: Actions → Manage Keys → Add Key → JSON
4. Save it here, e.g.: `acme-corp-sa.json`

Then either:

```bash
# Option A: Set env var (applies to all tenants)
export GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/AIREX/backend/config/credentials/acme-corp-sa.json

# Option B: Activate via gcloud (applies to all tenants)
gcloud auth activate-service-account --key-file=acme-corp-sa.json

# Option C: Per-tenant via Admin / API (recommended) — store the key path or inline
# config on the tenant's gcp_config JSON in PostgreSQL (replaces legacy tenants.yaml).
# Example path value: "services/airex-core/config/credentials/acme-corp-sa.json"
```

## AWS Credentials

### Method 1: Cross-Account Role Assumption (Recommended for multi-account)

The AIREX host assumes a role in the client's AWS account. No static keys stored.

**In the client's AWS account:**
1. Create an IAM role (e.g. `AirexReadOnly`) with these policies:
   - `AmazonSSMFullAccess` (or scoped `ssm:SendCommand` + `ssm:GetCommandInvocation`)
   - `AmazonEC2ReadOnlyAccess` (auto-discover instances by IP)
   - `CloudWatchLogsReadOnlyAccess` (query CloudWatch)
2. Set trust policy to allow the AIREX account/role to assume it:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": {"AWS": "arn:aws:iam::AIREX_ACCOUNT_ID:root"},
       "Action": "sts:AssumeRole",
       "Condition": {"StringEquals": {"sts:ExternalId": "airex-secret-id"}}
     }]
   }
   ```

**On the tenant record** (Admin UI or `PUT /api/v1/tenants/{name}`): set **`aws_config`** JSON, for example:
```json
{
  "account_id": "123456789012",
  "role_name": "AirexReadOnly",
  "external_id": "airex-secret-id",
  "region": "ap-south-1"
}
```

### Method 2: Access Key + Secret Key (for clients providing static keys)

1. Create a JSON file in this directory:

```json
{
  "access_key_id": "AKIA_EXAMPLE_KEY_ID",
  "secret_access_key": "wJaLrXUtnFEMI_EXAMPLE_SECRET"
}
```

Save as: `<tenant-name>-aws.json` (e.g. `delta-corp-aws.json`)

2. Reference the file path in the tenant's **`aws_config`** (e.g. `credentials_file`) via Admin or API.

### Method 3: Instance Role (for AIREX running on EC2/ECS)

Attach an IAM role to the AIREX host — no config needed.

### Method 4: AWS CLI Profile

```bash
aws configure --profile my-client
```
Then set **`profile`** (and related fields) on the tenant's **`aws_config`** in the database.

### Method 5: Environment Variables (applies to all tenants without explicit config)

```bash
export AWS_ACCESS_KEY_ID=AKIAxxxx
export AWS_SECRET_ACCESS_KEY=xxxx
export AWS_REGION=ap-south-1
```

## Required IAM Permissions

Both Role Assumption and Access Key methods need these permissions:

| Permission | Purpose |
|---|---|
| `ec2:DescribeInstances` | Auto-discover instance by private IP |
| `ec2:DescribeRegions` | List available regions |
| `ssm:SendCommand` | Run diagnostic commands via SSM |
| `ssm:GetCommandInvocation` | Get SSM command output |
| `ssm:DescribeInstanceInformation` | Check SSM agent status |
| `logs:FilterLogEvents` | Query CloudWatch Logs |
| `logs:DescribeLogGroups` | Discover log groups |

## File Naming Convention

```
<tenant-name>-sa.json          # GCP service account key
<tenant-name>-aws.json         # AWS access key credentials
<tenant-name>-ssh.pem          # SSH private key (fallback)
```

## Security

- This directory is in `.gitignore` — files here are never committed
- Set permissions: `chmod 600 *.json *.pem`
- Rotate keys regularly
- Prefer role assumption over static keys when possible
