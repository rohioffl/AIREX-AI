# Runbook: AWS EC2 Instance Connect (SSH fallback)

## When this applies

AIREX uses **EC2 Instance Connect** when:

- The incident target is AWS (from tags: `cloud:aws`, `ip:…`, `instance:i-…`), and
- **SSM is not available** (e.g. "InvalidInstanceId", "Instances not in a valid state").

No SSH keys are stored; a temporary key is pushed via the API and used for one session.

## Prerequisites

1. **IAM** — The role/user used by AIREX (tenant AWS config) must have:
   - `ec2-instance-connect:SendSSHPublicKey`
   - `ec2:DescribeInstances` (for discovery and resolving AZ)
2. **Instance** — Supported AMI (e.g. Amazon Linux 2, Ubuntu 16.04+) with EC2 Instance Connect.
3. **Network** — AIREX host can reach the instance **private IP** on port 22 (same VPC / peering / VPN).

## Diagnosis

1. **Check logs** for the incident:
   - `aws_ec2_connect_starting` — fallback is being used.
   - `aws_ec2_connect_send_key_failed` — API error (permissions or instance not supported).
   - `aws_ec2_connect_ssh_failed` — SSH failed (network, OS user, or instance not reachable).

2. **Verify IAM**:
   ```bash
   # Policy example (attach to AIREX role)
   {
     "Effect": "Allow",
     "Action": "ec2-instance-connect:SendSSHPublicKey",
     "Resource": "arn:aws:ec2:REGION:ACCOUNT:instance/*"
   }
   ```

3. **Verify instance**:
   - In EC2 console, open the instance → Connect → "EC2 Instance Connect" tab. If that works from the console, AIREX can use the same mechanism if IAM and network are correct.
   - Ensure the instance has a **private IP** and that the AIREX host can reach it (security groups, route tables).

4. **OS user** — Default is `ubuntu`. For Amazon Linux use `ec2-user`. Set **`ssh_user`** on the tenant record (Admin panel or tenant API).

## Remediation

| Symptom | Action |
|--------|--------|
| `SendSSHPublicKey` 400 / AuthException | Add or fix IAM policy above; check role assumption if cross-account. |
| `EC2InstanceNotFoundException` | Wrong region or instance ID; check discovery and tags. |
| SSH timeout / connection refused | Open port 22 from AIREX to instance private IP; check VPC/peering and security groups. |
| Wrong OS user | Set **`ssh_user`** on that tenant in the DB (Admin / `PUT /tenants/{name}`). |

## Optional: use SSM instead

To avoid EC2 Instance Connect entirely:

1. Install SSM Agent on the instance (default on Amazon Linux 2 and many Ubuntu AMIs).
2. Attach an IAM instance profile with `AmazonSSMManagedInstanceCore`.
3. Ensure the instance is registered in SSM (Systems Manager → Fleet Manager). After that, AIREX will use SSM first and will not fall back to EC2 Instance Connect.
