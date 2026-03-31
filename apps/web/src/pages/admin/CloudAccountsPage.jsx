import { useState, useEffect, useCallback, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import {
  Cloud, Plus, Trash2, RefreshCw, CheckCircle, AlertCircle,
  Key, ChevronDown, ChevronUp, Shield, Star, Loader, X, Eye, EyeOff,
  Copy, Check, Info, Plug,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import {
  fetchCloudAccounts,
  createCloudAccount,
  updateCloudAccount,
  updateCloudAccountCredentials,
  deleteCloudAccount,
  testCloudAccount,
  fetchIntegrations,
} from '../../services/api'

// ── AIREX principal identifiers (set via env vars) ─────────────────────────────
const AIREX_AWS_ACCOUNT_ID = import.meta.env.VITE_AIREX_AWS_ACCOUNT_ID || '547361935557'
const AIREX_AWS_PRINCIPAL   = `arn:aws:iam::${AIREX_AWS_ACCOUNT_ID}:root`
const AIREX_GCP_SA_EMAIL    = import.meta.env.VITE_AIREX_GCP_SA_EMAIL   || 'airex-runtime@airex-prod.iam.gserviceaccount.com'

// ── Helpers ────────────────────────────────────────────────────────────────────

const PROVIDER_META = {
  aws: { label: 'AWS', color: 'var(--neon-amber, #f59e0b)', bg: 'rgba(245,158,11,0.12)' },
  gcp: { label: 'GCP', color: 'var(--neon-cyan)', bg: 'rgba(34,211,238,0.1)' },
}

const MONITORING_ONBOARDING = {
  aws: [
    { key: 'cloudwatch', label: 'AWS CloudWatch', description: 'Connect CloudWatch alarms from this account.' },
    { key: 'pagerduty', label: 'PagerDuty', description: 'Use this if alerts route through PagerDuty first.' },
    { key: 'site24x7', label: 'Site24x7', description: 'Use this if uptime and infra alerts live in Site24x7.' },
  ],
  gcp: [
    { key: 'gcp_monitoring', label: 'GCP Cloud Monitoring', description: 'Connect Google Cloud Monitoring alerts for this project.' },
    { key: 'pagerduty', label: 'PagerDuty', description: 'Use this if GCP incidents are managed in PagerDuty first.' },
    { key: 'custom_webhook', label: 'Custom Webhook', description: 'Use this when your alert source can post webhooks into AIREX.' },
  ],
}

const NATIVE_INTEGRATION_KEYS = {
  aws: new Set(['cloudwatch']),
  gcp: new Set(['gcp_monitoring']),
}

const ACTIVE_INTEGRATION_TYPE_KEYS = new Set(['site24x7'])

function getAuthTypeLabel(binding) {
  if (binding.provider === 'aws') {
    return binding.has_static_credentials ? 'Static Keys' : 'IAM Role'
  }
  return binding.has_static_credentials ? 'Service Account' : 'Service Identity'
}

function getConnectionState(binding) {
  if (!binding.external_account_id?.trim()) {
    return { label: 'Incomplete', tone: 'attention' }
  }
  if (binding.provider === 'aws' && !binding.has_static_credentials && !binding.config_json?.role_arn) {
    return { label: 'Incomplete', tone: 'attention' }
  }
  return { label: 'Healthy', tone: 'healthy' }
}

function getMonitoringState(binding, integrations) {
  const providerNativeKeys = NATIVE_INTEGRATION_KEYS[binding.provider] || new Set()
  const activeIntegrations = integrations.filter(
    (integration) =>
      integration.enabled !== false &&
      integration.status !== 'disabled' &&
      integration.cloud_account_binding_id === binding.id
  )
  const nativeConnected = activeIntegrations.some((integration) => providerNativeKeys.has(integration.integration_type_key))
  const optionalConnected = activeIntegrations.some((integration) => !providerNativeKeys.has(integration.integration_type_key))

  return {
    native: { label: nativeConnected ? 'Connected' : 'Not Connected', tone: nativeConnected ? 'healthy' : 'attention' },
    optional: { label: optionalConnected ? 'Configured' : 'Not Configured', tone: optionalConnected ? 'healthy' : 'muted' },
  }
}

function getStatusColors(tone) {
  if (tone === 'healthy') {
    return {
      color: 'var(--neon-green)',
      border: 'rgba(34,197,94,0.3)',
      background: 'rgba(34,197,94,0.08)',
    }
  }
  if (tone === 'attention') {
    return {
      color: '#f59e0b',
      border: 'rgba(245,158,11,0.32)',
      background: 'rgba(245,158,11,0.08)',
    }
  }
  return {
    color: 'var(--text-muted)',
    border: 'var(--border)',
    background: 'var(--bg-elevated)',
  }
}

function StatusPill({ label, tone = 'muted' }) {
  const meta = getStatusColors(tone)
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '4px 9px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 700,
        border: `1px solid ${meta.border}`,
        background: meta.background,
        color: meta.color,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  )
}

function SummaryCard({ label, value, hint, tone = 'muted', action = null }) {
  const meta = getStatusColors(tone)
  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 12,
        background: 'var(--bg-card)',
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        minHeight: 122,
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: meta.color, letterSpacing: '-0.03em' }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        {hint}
      </div>
      {action}
    </div>
  )
}

function ActionRow({ title, subtitle, statusLabel, statusTone, actionLabel, onAction, disabled = false }) {
  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 12,
        background: 'var(--bg-card)',
        padding: '14px 15px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</span>
          <StatusPill label={statusLabel} tone={statusTone} />
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
          {subtitle}
        </div>
      </div>
      <button
        type="button"
        onClick={onAction}
        disabled={disabled}
        style={{
          flexShrink: 0,
          padding: '8px 12px',
          borderRadius: 8,
          border: disabled ? '1px solid var(--border)' : '1px solid rgba(34,211,238,0.28)',
          background: disabled ? 'var(--bg-elevated)' : 'rgba(34,211,238,0.08)',
          color: disabled ? 'var(--text-muted)' : 'var(--neon-cyan)',
          fontSize: 12,
          fontWeight: 700,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.8 : 1,
        }}
      >
        {actionLabel}
      </button>
    </div>
  )
}

function FilterChip({ label, active, onClick, count = null }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 700,
        cursor: 'pointer',
        border: `1px solid ${active ? 'var(--neon-cyan)' : 'var(--border)'}`,
        background: active ? 'rgba(34,211,238,0.1)' : 'var(--bg-card)',
        color: active ? 'var(--neon-cyan)' : 'var(--text-muted)',
      }}
    >
      {label}
      {count !== null && (
        <span style={{ fontSize: 11, color: active ? 'var(--neon-cyan)' : 'var(--text-secondary)' }}>
          {count}
        </span>
      )}
    </button>
  )
}

function ProviderBadge({ provider }) {
  const meta = PROVIDER_META[provider] || { label: provider.toUpperCase(), color: 'var(--text-muted)', bg: 'transparent' }
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
      border: `1px solid ${meta.color}`, color: meta.color, background: meta.bg,
      textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>
      {meta.label}
    </span>
  )
}

function SecretBadge({ hasCredentials }) {
  if (hasCredentials) {
    return (
      <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--neon-green)' }}>
        <Key size={12} />
        Static keys in SM
      </span>
    )
  }
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
      <Shield size={12} />
      Role / task IAM
    </span>
  )
}

// ── Forms ──────────────────────────────────────────────────────────────────────

function LabeledField({ label, hint, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
        {label}
        {hint && <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>{hint}</span>}
      </label>
      {children}
    </div>
  )
}

const INPUT_STYLE = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: 6,
  padding: '8px 10px',
  fontSize: 13,
  color: 'var(--text-primary)',
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}

function SecretInput({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false)
  return (
    <div style={{ position: 'relative' }}>
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        style={{ ...INPUT_STYLE, paddingRight: 36 }}
        autoComplete="new-password"
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        style={{
          position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)',
          display: 'flex', alignItems: 'center',
        }}
        tabIndex={-1}
      >
        {show ? <EyeOff size={14} /> : <Eye size={14} />}
      </button>
    </div>
  )
}

// ── CopyButton ─────────────────────────────────────────────────────────────────

function CopyButton({ text, size = 13 }) {
  const [copied, setCopied] = useState(false)
  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button
      type="button"
      onClick={handleCopy}
      title="Copy"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '2px 8px', borderRadius: 4,
        border: '1px solid var(--border)',
        background: copied ? 'rgba(34,211,238,0.1)' : 'var(--bg-elevated)',
        color: copied ? 'var(--neon-cyan)' : 'var(--text-muted)',
        fontSize: 11, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
        transition: 'all 0.15s',
      }}
    >
      {copied ? <Check size={size - 1} /> : <Copy size={size - 1} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

// ── Setup guides (shown for keyless / role-based auth) ─────────────────────────

function CodeBlock({ code }) {
  return (
    <div style={{ position: 'relative' }}>
      <pre style={{
        margin: 0, padding: '10px 12px',
        background: 'rgba(0,0,0,0.35)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        fontSize: 11, lineHeight: 1.6,
        color: 'var(--text-primary)',
        overflowX: 'auto',
        fontFamily: 'monospace',
        whiteSpace: 'pre',
      }}>
        {code}
      </pre>
      <div style={{ position: 'absolute', top: 6, right: 8 }}>
        <CopyButton text={code} />
      </div>
    </div>
  )
}

function SetupStep({ num, title, children }) {
  return (
    <div style={{ display: 'flex', gap: 10 }}>
      <div style={{
        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
        background: 'rgba(34,211,238,0.15)', border: '1px solid rgba(34,211,238,0.35)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 800, color: 'var(--neon-cyan)', marginTop: 1,
      }}>
        {num}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>{title}</div>
        {children}
      </div>
    </div>
  )
}

const CLI_INSTALL = {
  aws: `# macOS (Homebrew)
brew install awscli

# Linux (x86_64)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install

# Verify
aws --version

# Configure credentials
aws configure`,

  gcloud: `# macOS (Homebrew)
brew install --cask google-cloud-sdk

# Linux (Debian / Ubuntu)
sudo apt-get install -y apt-transport-https ca-certificates gnupg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \\
  https://packages.cloud.google.com/apt cloud-sdk main" \\
  | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \\
  | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
sudo apt-get update && sudo apt-get install google-cloud-cli

# Verify
gcloud --version

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID`,
}

function CliInstallHint({ provider }) {
  const [open, setOpen] = useState(false)
  const label = provider === 'aws' ? 'AWS CLI' : 'gcloud CLI'
  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: 11, color: 'var(--text-muted)', padding: 0,
        }}
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {open ? `Hide ${label} install instructions` : `Don't have ${label} installed?`}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          <CodeBlock code={CLI_INSTALL[provider]} />
        </div>
      )}
    </div>
  )
}

function AwsRoleSetupGuide({ externalId }) {
  const trustPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Principal: { AWS: AIREX_AWS_PRINCIPAL },
      Action: 'sts:AssumeRole',
      ...(externalId ? {
        Condition: { StringEquals: { 'sts:ExternalId': externalId } },
      } : {}),
    }],
  }, null, 2)

  const permissionsPolicy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Effect: 'Allow',
      Action: [
        'ec2:Describe*',
        'ssm:SendCommand', 'ssm:GetCommandInvocation', 'ssm:DescribeInstanceInformation',
        'cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics',
        'logs:GetLogEvents', 'logs:DescribeLogGroups', 'logs:DescribeLogStreams',
      ],
      Resource: '*',
    }],
  }, null, 2)

  return (
    <div style={{
      background: 'rgba(34,211,238,0.03)',
      border: '1px solid rgba(34,211,238,0.18)',
      borderRadius: 8, padding: 14,
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: -2 }}>
        <Info size={13} style={{ color: 'var(--neon-cyan)', flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--neon-cyan)' }}>
          Setup required in your AWS account
        </span>
      </div>

      <SetupStep num={1} title="Create an IAM Role in your AWS account">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          IAM → Roles → Create role → <strong style={{ color: 'var(--text-secondary)' }}>Another AWS account</strong>
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>AIREX account ID:</span>
          <code style={{ fontSize: 12, fontWeight: 700, color: 'var(--neon-cyan)', background: 'rgba(34,211,238,0.08)', padding: '2px 8px', borderRadius: 4 }}>
            {AIREX_AWS_ACCOUNT_ID}
          </code>
          <CopyButton text={AIREX_AWS_ACCOUNT_ID} />
        </div>
      </SetupStep>

      <SetupStep num={2} title="Paste this trust policy on the role">
        <CodeBlock code={trustPolicy} />
      </SetupStep>

      <SetupStep num={3} title="Attach a permissions policy to the role">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          Use <strong style={{ color: 'var(--text-secondary)' }}>ReadOnlyAccess</strong> (AWS managed) or a custom policy with minimum required actions:
        </p>
        <CodeBlock code={permissionsPolicy} />
      </SetupStep>

      <SetupStep num={4} title="Copy the Role ARN and paste it below" >
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          e.g. <code style={{ color: 'var(--text-secondary)' }}>arn:aws:iam::123456789012:role/AirexReadOnly</code>
        </p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 6px' }}>Or create the role entirely via CLI:</p>
        <CodeBlock code={`# Save trust-policy.json first (copy from step 2 above), then:\naws iam create-role \\\n  --role-name AirexReadOnly \\\n  --assume-role-policy-document file://trust-policy.json\n\naws iam attach-role-policy \\\n  --role-name AirexReadOnly \\\n  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess\n\n# Get the Role ARN:\naws iam get-role --role-name AirexReadOnly \\\n  --query 'Role.Arn' --output text`} />
      </SetupStep>

      <CliInstallHint provider="aws" />
    </div>
  )
}

function AwsAccessKeySetupGuide() {
  const policy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [{
      Sid: 'AirexAccess',
      Effect: 'Allow',
      Action: [
        'ec2:Describe*',
        'ssm:SendCommand',
        'ssm:GetCommandInvocation',
        'ssm:DescribeInstanceInformation',
        'ssm:ListDocuments',
        'cloudwatch:GetMetricStatistics',
        'cloudwatch:ListMetrics',
        'cloudwatch:DescribeAlarms',
        'logs:GetLogEvents',
        'logs:DescribeLogGroups',
        'logs:DescribeLogStreams',
        'logs:FilterLogEvents',
      ],
      Resource: '*',
    }],
  }, null, 2)

  return (
    <div style={{
      background: 'rgba(245,158,11,0.03)',
      border: '1px solid rgba(245,158,11,0.2)',
      borderRadius: 8, padding: 14,
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: -2 }}>
        <Info size={13} style={{ color: '#f59e0b', flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b' }}>
          Setup required in your AWS account
        </span>
      </div>

      <SetupStep num={1} title="Create an IAM user for AIREX">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
          IAM → Users → Create user → choose <strong style={{ color: 'var(--text-secondary)' }}>Attach policies directly</strong>
        </p>
      </SetupStep>

      <SetupStep num={2} title="Attach this inline or customer-managed policy">
        <CodeBlock code={policy} />
      </SetupStep>

      <SetupStep num={3} title="Create an access key for the user">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          IAM → Users → [user] → Security credentials → Create access key →{' '}
          <strong style={{ color: 'var(--text-secondary)' }}>Third-party service</strong>.
          Copy the Access Key ID and Secret, then paste them below.
        </p>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
          Or via CLI:
        </p>
        <CodeBlock code={`aws iam create-access-key --user-name airex-user`} />
      </SetupStep>

      <CliInstallHint provider="aws" />
    </div>
  )
}

function GcpSaJsonSetupGuide() {
  const gcloudRoles = ['roles/compute.viewer', 'roles/logging.viewer', 'roles/monitoring.viewer', 'roles/iam.serviceAccountTokenCreator']
  const createCmd = `# 1. Create the service account\ngcloud iam service-accounts create airex-reader \\\n  --display-name="AIREX Reader" \\\n  --project=YOUR_PROJECT_ID`
  const bindCmds = gcloudRoles.map((role) =>
    `gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \\\n  --member="serviceAccount:airex-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com" \\\n  --role="${role}"`
  ).join('\n\n')
  const keyCmd = `# 3. Generate and download the JSON key\ngcloud iam service-accounts keys create airex-key.json \\\n  --iam-account=airex-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com`

  return (
    <div style={{
      background: 'rgba(245,158,11,0.03)',
      border: '1px solid rgba(245,158,11,0.2)',
      borderRadius: 8, padding: 14,
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: -2 }}>
        <Info size={13} style={{ color: '#f59e0b', flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#f59e0b' }}>
          Setup required in your GCP project
        </span>
      </div>

      <SetupStep num={1} title="Create a dedicated service account">
        <CodeBlock code={createCmd} />
      </SetupStep>

      <SetupStep num={2} title="Grant required roles to the service account">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          Replace <code style={{ color: 'var(--text-secondary)' }}>YOUR_PROJECT_ID</code> throughout:
        </p>
        <CodeBlock code={bindCmds} />
      </SetupStep>

      <SetupStep num={3} title="Download the JSON key and paste it below">
        <CodeBlock code={keyCmd} />
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
          Then open <code style={{ color: 'var(--text-secondary)' }}>airex-key.json</code> and paste its full contents in the field below.
        </p>
      </SetupStep>

      <CliInstallHint provider="gcloud" />
    </div>
  )
}

function GcpSaSetupGuide() {
  const gcloudRoles = ['roles/compute.viewer', 'roles/logging.viewer', 'roles/monitoring.viewer', 'roles/iam.serviceAccountTokenCreator']
  const gcloudCommands = gcloudRoles.map((role) =>
    `gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \\\n  --member="serviceAccount:${AIREX_GCP_SA_EMAIL}" \\\n  --role="${role}"`
  ).join('\n\n')

  return (
    <div style={{
      background: 'rgba(34,211,238,0.03)',
      border: '1px solid rgba(34,211,238,0.18)',
      borderRadius: 8, padding: 14,
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: -2 }}>
        <Info size={13} style={{ color: 'var(--neon-cyan)', flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--neon-cyan)' }}>
          Setup required in your GCP project
        </span>
      </div>

      <SetupStep num={1} title="Grant AIREX's service account access to your project">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          AIREX uses this service account to access your GCP resources:
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <code style={{ fontSize: 11, fontWeight: 700, color: 'var(--neon-cyan)', background: 'rgba(34,211,238,0.08)', padding: '2px 8px', borderRadius: 4, wordBreak: 'break-all' }}>
            {AIREX_GCP_SA_EMAIL}
          </code>
          <CopyButton text={AIREX_GCP_SA_EMAIL} />
        </div>
      </SetupStep>

      <SetupStep num={2} title="Run these gcloud commands (Cloud Shell or local CLI)">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          Replace <code style={{ color: 'var(--text-secondary)' }}>YOUR_PROJECT_ID</code> with your GCP project ID:
        </p>
        <CodeBlock code={gcloudCommands} />
      </SetupStep>

      <SetupStep num={3} title="Enter your GCP Project ID in the field below">
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
          The project ID (not name) — found in the GCP console header or via{' '}
          <code style={{ color: 'var(--text-secondary)' }}>gcloud config get-value project</code>
        </p>
      </SetupStep>

      <CliInstallHint provider="gcloud" />
    </div>
  )
}

// ── AddBindingModal ────────────────────────────────────────────────────────────

const CRED_TYPES = {
  aws: [
    {
      id: 'role',
      label: 'IAM Role Assumption',
      desc: 'AIREX assumes a cross-account role via STS. No keys stored — recommended.',
      icon: Shield,
      color: 'var(--neon-cyan)',
      bg: 'rgba(34,211,238,0.06)',
      border: 'rgba(34,211,238,0.3)',
    },
    {
      id: 'keys',
      label: 'Access Keys',
      desc: 'Static Access Key ID + Secret stored encrypted in Secrets Manager.',
      icon: Key,
      color: '#f59e0b',
      bg: 'rgba(245,158,11,0.06)',
      border: 'rgba(245,158,11,0.3)',
    },
  ],
  gcp: [
    {
      id: 'role',
      label: 'Workload Identity / Instance SA',
      desc: 'Use the ambient service account attached to the AIREX runtime. No keys stored.',
      icon: Shield,
      color: 'var(--neon-cyan)',
      bg: 'rgba(34,211,238,0.06)',
      border: 'rgba(34,211,238,0.3)',
    },
    {
      id: 'keys',
      label: 'Service Account JSON',
      desc: 'Upload a service account key file — stored encrypted in Secrets Manager.',
      icon: Key,
      color: '#f59e0b',
      bg: 'rgba(245,158,11,0.06)',
      border: 'rgba(245,158,11,0.3)',
    },
  ],
}

function AddBindingModal({ onClose, onCreated, onLaunchIntegration, tenantId = null }) {
  const [provider, setProvider] = useState('aws')
  const [credType, setCredType] = useState('role')
  const [displayName, setDisplayName] = useState('')
  const [externalAccountId, setExternalAccountId] = useState('')

  // AWS role fields
  const [awsRegion, setAwsRegion] = useState('ap-south-1')
  const [awsRoleArn, setAwsRoleArn] = useState('')
  const [awsExternalId, setAwsExternalId] = useState('')

  // AWS access key fields
  const [awsAccessKeyId, setAwsAccessKeyId] = useState('')
  const [awsSecretAccessKey, setAwsSecretAccessKey] = useState('')

  // GCP fields
  const [gcpZone, setGcpZone] = useState('')
  const [gcpSaJson, setGcpSaJson] = useState('')
  const [gcpSaJsonError, setGcpSaJsonError] = useState('')

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [createdBinding, setCreatedBinding] = useState(null)

  function switchProvider(p) {
    setProvider(p)
    setCredType('role')
  }

  function buildPayload() {
    const config_json =
      provider === 'aws'
        ? { region: awsRegion || undefined, role_arn: awsRoleArn || undefined, external_id: awsExternalId || undefined }
        : { zone: gcpZone || undefined }

    Object.keys(config_json).forEach((k) => config_json[k] === undefined && delete config_json[k])

    const payload = { provider, display_name: displayName.trim(), external_account_id: externalAccountId.trim(), config_json }

    if (provider === 'aws' && credType === 'keys') {
      payload.aws_credentials = { access_key_id: awsAccessKeyId, secret_access_key: awsSecretAccessKey }
    }

    if (provider === 'gcp' && credType === 'keys') {
      try {
        payload.gcp_credentials = JSON.parse(gcpSaJson)
        setGcpSaJsonError('')
      } catch {
        setGcpSaJsonError('Invalid JSON — paste the full service account key file.')
        return null
      }
    }

    return payload
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!displayName.trim()) { setError('Display name is required.'); return }
    if (!externalAccountId.trim()) {
      setError(provider === 'aws' ? 'AWS Account ID is required.' : 'GCP Project ID is required.')
      return
    }
    const payload = buildPayload()
    if (!payload) return
    setSaving(true)
    try {
      const binding = await createCloudAccount(payload, tenantId)
      onCreated(binding)
      setCreatedBinding(binding)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to create cloud account.')
    } finally {
      setSaving(false)
    }
  }

  const credOptions = CRED_TYPES[provider]
  const monitoringRecommendations = MONITORING_ONBOARDING[createdBinding?.provider || provider] || []

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 12, width: '100%', maxWidth: 620,
        maxHeight: '90vh', overflowY: 'auto', padding: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
              {createdBinding ? 'Connect Monitoring' : 'Add Cloud Account'}
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
              {createdBinding
                ? 'Step 2 of 2: choose the monitoring source that should send alerts for this tenant.'
                : 'Step 1 of 2: connect cloud credentials first.'}
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        {!createdBinding ? (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

          {/* Provider */}
          <LabeledField label="Provider">
            <div style={{ display: 'flex', gap: 8 }}>
              {['aws', 'gcp'].map((p) => (
                <button key={p} type="button" onClick={() => switchProvider(p)} style={{
                  flex: 1, padding: '8px 0', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  border: `1px solid ${provider === p ? PROVIDER_META[p].color : 'var(--border)'}`,
                  background: provider === p ? PROVIDER_META[p].bg : 'var(--bg-elevated)',
                  color: provider === p ? PROVIDER_META[p].color : 'var(--text-secondary)',
                }}>
                  {PROVIDER_META[p].label}
                </button>
              ))}
            </div>
          </LabeledField>

          {/* Credential type cards */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
              Authentication Method
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {credOptions.map(({ id, label, desc, icon: Icon, color, bg, border }) => {
                const active = credType === id
                return (
                  <button key={id} type="button" onClick={() => setCredType(id)} style={{
                    textAlign: 'left', padding: '14px', borderRadius: 8, cursor: 'pointer',
                    border: `1.5px solid ${active ? border : 'var(--border)'}`,
                    background: active ? bg : 'var(--bg-elevated)',
                    transition: 'all 0.15s',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
                      <Icon size={14} style={{ color: active ? color : 'var(--text-muted)', flexShrink: 0 }} />
                      <span style={{ fontSize: 12, fontWeight: 700, color: active ? color : 'var(--text-secondary)' }}>
                        {label}
                      </span>
                    </div>
                    <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>{desc}</p>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Common fields */}
          <LabeledField label="Display Name" hint="e.g. Production AWS, Staging GCP">
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              placeholder={provider === 'aws' ? 'Production AWS' : 'Production GCP'}
              style={INPUT_STYLE} required />
          </LabeledField>

          {provider === 'aws' && (
            <LabeledField label="AWS Account ID" hint="required">
              <input value={externalAccountId} onChange={(e) => setExternalAccountId(e.target.value)}
                placeholder="123456789012"
                style={INPUT_STYLE}
                required />
            </LabeledField>
          )}

          {/* AWS fields */}
          {provider === 'aws' && (
            <>
              {credType === 'role' && <AwsRoleSetupGuide externalId={awsExternalId} />}

              <LabeledField label="Primary AWS Region">
                <input value={awsRegion} onChange={(e) => setAwsRegion(e.target.value)}
                  placeholder="ap-south-1" style={INPUT_STYLE} />
              </LabeledField>

              {credType === 'role' && (
                <>
                  <LabeledField label="External ID" hint="optional — add to trust policy condition above">
                    <input value={awsExternalId} onChange={(e) => setAwsExternalId(e.target.value)}
                      placeholder="airex-external-id" style={INPUT_STYLE} />
                  </LabeledField>
                  <LabeledField label="Role ARN" hint="from the role you created above">
                    <input value={awsRoleArn} onChange={(e) => setAwsRoleArn(e.target.value)}
                      placeholder="arn:aws:iam::123456789012:role/AirexReadOnly"
                      style={INPUT_STYLE} />
                  </LabeledField>
                </>
              )}

              {credType === 'keys' && (
                <>
                  <AwsAccessKeySetupGuide />
                  <LabeledField label="Access Key ID">
                    <input value={awsAccessKeyId} onChange={(e) => setAwsAccessKeyId(e.target.value)}
                      placeholder="AKIAIOSFODNN7EXAMPLE" style={INPUT_STYLE} autoComplete="off" />
                  </LabeledField>
                  <LabeledField label="Secret Access Key">
                    <SecretInput value={awsSecretAccessKey} onChange={(e) => setAwsSecretAccessKey(e.target.value)}
                      placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" />
                  </LabeledField>
                </>
              )}
            </>
          )}

          {/* GCP fields */}
          {provider === 'gcp' && (
            <>
              {credType === 'role' && <GcpSaSetupGuide />}

              <LabeledField label="GCP Project ID" hint="your project, not AIREX's">
                <input value={externalAccountId} onChange={(e) => setExternalAccountId(e.target.value)}
                  placeholder="my-gcp-project-id" style={INPUT_STYLE} required />
              </LabeledField>

              <LabeledField label="Zone" hint="e.g. us-central1-a">
                <input value={gcpZone} onChange={(e) => setGcpZone(e.target.value)}
                  placeholder="us-central1-a" style={INPUT_STYLE} />
              </LabeledField>

              {credType === 'keys' && (
                <>
                  <GcpSaJsonSetupGuide />
                  <LabeledField label="Service Account JSON" hint="paste the full key file content">
                    <textarea value={gcpSaJson}
                      onChange={(e) => { setGcpSaJson(e.target.value); setGcpSaJsonError('') }}
                      placeholder='{"type": "service_account", "project_id": "...", ...}'
                      style={{ ...INPUT_STYLE, minHeight: 120, resize: 'vertical', fontFamily: 'monospace', fontSize: 11 }} />
                    {gcpSaJsonError && <span style={{ fontSize: 11, color: '#ef4444' }}>{gcpSaJsonError}</span>}
                  </LabeledField>
                </>
              )}
            </>
          )}

          {error && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 6, padding: '8px 12px', fontSize: 12, color: '#ef4444' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 4 }}>
            <button type="button" onClick={onClose}
              style={{ padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving} style={{
              padding: '8px 18px', borderRadius: 6, border: 'none',
              background: saving ? 'var(--border)' : 'var(--neon-cyan)',
              color: saving ? 'var(--text-muted)' : '#000', fontSize: 13, fontWeight: 600,
              cursor: saving ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              {saving && <Loader size={13} className="animate-spin" />}
              {saving ? 'Creating…' : 'Create Account'}
            </button>
          </div>
        </form>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{
              border: '1px solid rgba(34,197,94,0.28)',
              background: 'rgba(34,197,94,0.08)',
              borderRadius: 10,
              padding: '14px 16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <CheckCircle size={15} style={{ color: 'var(--neon-green)' }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
                  {createdBinding.display_name} is connected
                </span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                Keep going in the same flow and connect the monitoring source that should create incidents for this tenant.
              </p>
            </div>

            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Recommended Monitoring Sources
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10 }}>
                {monitoringRecommendations.map((integration) => (
                  <button
                    key={integration.key}
                    type="button"
                    onClick={() => {
                      onLaunchIntegration?.(integration.key, createdBinding.id)
                      onClose()
                    }}
                    style={{
                      textAlign: 'left',
                      padding: '14px',
                      borderRadius: 10,
                      border: '1px solid rgba(34,211,238,0.22)',
                      background: 'var(--bg-elevated)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Plug size={14} style={{ color: 'var(--neon-cyan)', flexShrink: 0 }} />
                        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
                          {integration.label}
                        </span>
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--neon-cyan)', fontWeight: 700 }}>
                        Configure
                      </span>
                    </div>
                    <p style={{ margin: '6px 0 0', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      {integration.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => setCreatedBinding(null)}
                style={{ padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer' }}
              >
                Back
              </button>
              <button
                type="button"
                onClick={onClose}
                style={{ padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--neon-cyan)', color: '#000', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
              >
                Finish Later
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}

// ── RotateCredentialsModal ─────────────────────────────────────────────────────

function RotateCredentialsModal({ binding, onClose, onRotated, tenantId = null }) {
  const isAws = binding.provider === 'aws'
  const [awsAccessKeyId, setAwsAccessKeyId] = useState('')
  const [awsSecretAccessKey, setAwsSecretAccessKey] = useState('')
  const [gcpSaJson, setGcpSaJson] = useState('')
  const [gcpSaJsonError, setGcpSaJsonError] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    let payload = {}

    if (isAws) {
      if (!awsAccessKeyId || !awsSecretAccessKey) {
        setError('Both Access Key ID and Secret Access Key are required.')
        return
      }
      payload = { aws_credentials: { access_key_id: awsAccessKeyId, secret_access_key: awsSecretAccessKey } }
    } else {
      try {
        payload = { gcp_credentials: JSON.parse(gcpSaJson) }
        setGcpSaJsonError('')
      } catch {
        setGcpSaJsonError('Invalid JSON.')
        return
      }
    }

    setSaving(true)
    try {
      const updated = await updateCloudAccountCredentials(binding.id, payload, tenantId)
      onRotated(updated)
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to rotate credentials.')
    } finally {
      setSaving(false)
    }
  }

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 12, width: '100%', maxWidth: 480, padding: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
            Rotate Credentials — {binding.display_name}
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
          New credentials will be written to AWS Secrets Manager and replace any previously stored value.
          The secret ARN stays the same.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {isAws ? (
            <>
              <LabeledField label="Access Key ID">
                <input
                  value={awsAccessKeyId}
                  onChange={(e) => setAwsAccessKeyId(e.target.value)}
                  placeholder="AKIAIOSFODNN7EXAMPLE"
                  style={INPUT_STYLE}
                  autoComplete="off"
                />
              </LabeledField>
              <LabeledField label="Secret Access Key">
                <SecretInput
                  value={awsSecretAccessKey}
                  onChange={(e) => setAwsSecretAccessKey(e.target.value)}
                  placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                />
              </LabeledField>
            </>
          ) : (
            <LabeledField label="Service Account JSON" hint="paste the full key file content">
              <textarea
                value={gcpSaJson}
                onChange={(e) => { setGcpSaJson(e.target.value); setGcpSaJsonError('') }}
                placeholder='{"type": "service_account", ...}'
                style={{ ...INPUT_STYLE, minHeight: 120, resize: 'vertical', fontFamily: 'monospace', fontSize: 11 }}
              />
              {gcpSaJsonError && <span style={{ fontSize: 11, color: '#ef4444' }}>{gcpSaJsonError}</span>}
            </LabeledField>
          )}

          {error && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 6, padding: '8px 12px', fontSize: 12, color: '#ef4444' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={onClose}
              style={{ padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{
                padding: '8px 18px', borderRadius: 6, border: 'none',
                background: saving ? 'var(--border)' : '#f59e0b',
                color: '#000', fontSize: 13, fontWeight: 600,
                cursor: saving ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {saving && <Loader size={13} className="animate-spin" />}
              {saving ? 'Saving…' : 'Rotate Credentials'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

// ── BindingCard ────────────────────────────────────────────────────────────────

function BindingCard({ binding, integrations, onDelete, onRotate, onSetDefault, onLaunchIntegration, tenantId = null }) {
  const [expanded, setExpanded] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteSecret, setDeleteSecret] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function handleTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testCloudAccount(binding.id, tenantId)
      setTestResult({ ok: true, detail: res.detail })
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Connection test failed.'
      setTestResult({ ok: false, detail: msg })
    } finally {
      setTesting(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteCloudAccount(binding.id, deleteSecret, tenantId)
      onDelete(binding.id)
    } catch {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const configEntries = Object.entries(binding.config_json || {}).filter(([, v]) => v !== undefined && v !== '')
  const connectionState = getConnectionState(binding)
  const monitoringState = getMonitoringState(binding, integrations)
  const authType = getAuthTypeLabel(binding)
  const lastVerifiedLabel = binding.updated_at ? new Date(binding.updated_at).toLocaleString() : 'Not yet recorded'
  const nativeLabel = binding.provider === 'aws' ? 'CloudWatch' : 'Cloud Monitoring'

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 10, overflow: 'hidden',
      borderLeft: `3px solid ${binding.is_default ? 'var(--neon-cyan)' : 'var(--border)'}`,
    }}>
      {/* Header row */}
      <div
        style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 14, cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, minWidth: 0, flex: 1 }}>
            <ProviderBadge provider={binding.provider} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)' }}>
                  {binding.display_name}
                </span>
                {binding.is_default && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--neon-cyan)', fontWeight: 700 }}>
                    <Star size={10} />
                    DEFAULT
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                {binding.external_account_id}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <SecretBadge hasCredentials={binding.has_static_credentials} />
            <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>
              {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Auth Type
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{authType}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Native Monitoring
            </span>
            <StatusPill label={`${nativeLabel} ${monitoringState.native.label}`} tone={monitoringState.native.tone} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Optional Monitoring
            </span>
            <StatusPill label={monitoringState.optional.label} tone={monitoringState.optional.tone} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Connection Status
            </span>
            <StatusPill label={connectionState.label} tone={connectionState.tone} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Last Verified
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{lastVerifiedLabel}</span>
          </div>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Config summary */}
          {configEntries.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {configEntries.map(([k, v]) => (
                <span key={k} style={{
                  fontSize: 11, background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  borderRadius: 4, padding: '2px 7px', color: 'var(--text-secondary)',
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>{k}: </span>
                  {String(v)}
                </span>
              ))}
            </div>
          )}

          {/* ARN masked */}
          {binding.credentials_secret_arn_masked && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
              SM ARN: {binding.credentials_secret_arn_masked}
            </div>
          )}

          {/* Test result */}
          {testResult && (
            <div style={{
              background: testResult.ok ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
              border: `1px solid ${testResult.ok ? '#22c55e' : '#ef4444'}`,
              borderRadius: 6, padding: '8px 12px', fontSize: 12,
              color: testResult.ok ? '#22c55e' : '#ef4444',
              display: 'flex', alignItems: 'flex-start', gap: 6,
            }}>
              {testResult.ok ? <CheckCircle size={13} style={{ marginTop: 1, flexShrink: 0 }} /> : <AlertCircle size={13} style={{ marginTop: 1, flexShrink: 0 }} />}
              {testResult.detail}
            </div>
          )}

          {/* Action row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <button
              onClick={() => onLaunchIntegration?.(binding.provider === 'aws' ? 'cloudwatch' : 'gcp_monitoring', binding.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                border: '1px solid rgba(34,211,238,0.28)', background: 'rgba(34,211,238,0.08)', color: 'var(--neon-cyan)',
              }}
            >
              <Plug size={12} />
              Manage Monitoring
            </button>

            <button
              onClick={handleTest}
              disabled={testing}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 12px', borderRadius: 6, fontSize: 12, cursor: testing ? 'not-allowed' : 'pointer',
                border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
              }}
            >
              {testing ? <Loader size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Test Connection
            </button>

            <button
              onClick={() => onRotate(binding)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                border: '1px solid #f59e0b', background: 'rgba(245,158,11,0.08)', color: '#f59e0b',
              }}
            >
              <Key size={12} />
              Rotate Secret
            </button>

            {!binding.is_default && (
              <button
                onClick={() => onSetDefault(binding)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '5px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  border: '1px solid var(--neon-cyan)', background: 'rgba(34,211,238,0.06)', color: 'var(--neon-cyan)',
                }}
              >
                <Star size={12} />
                Set as Default
              </button>
            )}

            {!confirmDelete ? (
              <button
                onClick={() => setConfirmDelete(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5, marginLeft: 'auto',
                  padding: '5px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  border: '1px solid #ef4444', background: 'rgba(239,68,68,0.08)', color: '#ef4444',
                }}
              >
                <Trash2 size={12} />
                Delete
              </button>
            ) : (
              <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={deleteSecret} onChange={(e) => setDeleteSecret(e.target.checked)} />
                  Also delete SM secret (14-day recovery)
                </label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    style={{ padding: '4px 10px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    style={{ padding: '4px 10px', borderRadius: 5, border: 'none', background: '#ef4444', color: '#fff', fontSize: 12, fontWeight: 600, cursor: deleting ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    {deleting && <Loader size={11} className="animate-spin" />}
                    Confirm Delete
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── CloudAccountsPage ──────────────────────────────────────────────────────────

export default function CloudAccountsPage({
  tenantId: propTenantId = null,
  embedded = false,
  _externalShowAdd = false,
  _onExternalShowAddDone = null,
  onLaunchIntegration = null,
}) {
  const { activeTenant } = useAuth()
  const navigate = useNavigate()
  const tenantId = propTenantId || activeTenant?.id
  const [bindings, setBindings] = useState([])
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [integrationsLoading, setIntegrationsLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [rotatingBinding, setRotatingBinding] = useState(null)
  const [providerFilter, setProviderFilter] = useState('all')
  const [healthFilter, setHealthFilter] = useState('all')

  useEffect(() => {
    if (_externalShowAdd) {
      setShowAdd(true)
      _onExternalShowAddDone?.()
    }
  }, [_externalShowAdd, _onExternalShowAddDone])

  const loadBindings = useCallback(async () => {
    if (!tenantId) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchCloudAccounts(providerFilter !== 'all' ? providerFilter : null, tenantId)
      setBindings(data || [])
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load cloud accounts.')
    } finally {
      setLoading(false)
    }
  }, [providerFilter, tenantId])

  const loadIntegrations = useCallback(async () => {
    if (!tenantId) return
    setIntegrationsLoading(true)
    try {
      const data = await fetchIntegrations(tenantId)
      setIntegrations(data || [])
    } catch {
      setIntegrations([])
    } finally {
      setIntegrationsLoading(false)
    }
  }, [tenantId])

  useEffect(() => {
    setBindings([])
    loadBindings()
  }, [loadBindings])

  useEffect(() => {
    setIntegrations([])
    loadIntegrations()
  }, [loadIntegrations])

  const hasActiveIntegration = useCallback(
    (integrationTypeKey) => integrations.some(
      (integration) => integration.enabled !== false && integration.integration_type_key === integrationTypeKey
    ),
    [integrations]
  )

  const isAvailableIntegration = useCallback(
    (integrationTypeKey) => ACTIVE_INTEGRATION_TYPE_KEYS.has(integrationTypeKey),
    []
  )

  function handleCreated(binding) {
    setBindings((prev) => [binding, ...prev])
  }

  function handleDeleted(id) {
    setBindings((prev) => prev.filter((b) => b.id !== id))
  }

  function handleRotated(updated) {
    setBindings((prev) => prev.map((b) => (b.id === updated.id ? updated : b)))
  }

  async function handleSetDefault(binding) {
    try {
      const updated = await updateCloudAccount(binding.id, { is_default: true }, tenantId)
      setBindings((prev) =>
        prev.map((b) => {
          if (b.provider !== binding.provider) return b
          if (b.id === updated.id) return updated
          return { ...b, is_default: false }
        })
      )
    } catch {
      // ignore — UI stays consistent
    }
  }

  const bindingsWithState = useMemo(
    () => bindings.map((binding) => ({
      ...binding,
      _connectionState: getConnectionState(binding),
      _monitoringState: getMonitoringState(binding, integrations),
    })),
    [bindings, integrations],
  )

  const counts = useMemo(() => ({
    all: bindingsWithState.length,
    aws: bindingsWithState.filter((binding) => binding.provider === 'aws').length,
    gcp: bindingsWithState.filter((binding) => binding.provider === 'gcp').length,
    healthy: bindingsWithState.filter((binding) => binding._connectionState.label === 'Healthy').length,
    attention: bindingsWithState.filter((binding) => binding._connectionState.label !== 'Healthy').length,
  }), [bindingsWithState])

  const filtered = bindingsWithState.filter((binding) => {
    if (providerFilter !== 'all' && binding.provider !== providerFilter) return false
    if (healthFilter === 'healthy' && binding._connectionState.label !== 'Healthy') return false
    if (healthFilter === 'attention' && binding._connectionState.label === 'Healthy') return false
    return true
  })

  const launchMonitoring = useCallback((key, bindingId = null) => {
    if (onLaunchIntegration) {
      onLaunchIntegration(key, bindingId)
      return
    }
    const params = new URLSearchParams()
    if (key) params.set('integration', key)
    if (bindingId) params.set('binding', bindingId)
    const suffix = params.toString()
    navigate(`/admin/integrations${suffix ? `?${suffix}` : ''}`)
  }, [navigate, onLaunchIntegration])

  if (!tenantId) {
    return (
      <div style={{ textAlign: 'center', padding: '64px 24px', color: 'var(--text-muted)' }}>
        <Cloud size={40} style={{ margin: '0 auto 12px', display: 'block', opacity: 0.3 }} />
        <p style={{ fontSize: 14 }}>No workspace selected. Switch to a workspace to manage cloud accounts.</p>
      </div>
    )
  }

  const tenantLabel = propTenantId ? null : (activeTenant?.display_name || activeTenant?.name || activeTenant?.slug || activeTenant?.id)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header — hidden when embedded inside a stage layout */}
      {!embedded && (
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 10, margin: 0 }}>
              <Cloud size={24} style={{ color: 'var(--text-muted)' }} />
              Cloud Accounts
              {tenantLabel && <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)', letterSpacing: 0 }}>— {tenantLabel}</span>}
            </h2>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
              Linked AWS accounts and GCP projects. Credentials are stored in AWS Secrets Manager — never in the database.
            </p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '9px 16px', borderRadius: 8, border: 'none',
              background: 'var(--neon-cyan)', color: '#000',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            <Plus size={14} />
            Onboard Account
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(300px, 1fr)', gap: 16, alignItems: 'start' }}>
        <section style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-card)', overflow: 'hidden' }}>
          <div style={{ padding: '18px 18px 14px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Zone A
                </div>
                <h3 style={{ margin: '6px 0 0', fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>
                  Onboarded Accounts
                </h3>
                <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-secondary)', maxWidth: 640 }}>
                  Review connected cloud accounts, verify access, and launch monitoring setup from the same surface.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
              <FilterChip label="All" count={counts.all} active={providerFilter === 'all' && healthFilter === 'all'} onClick={() => { setProviderFilter('all'); setHealthFilter('all') }} />
              <FilterChip label="AWS" count={counts.aws} active={providerFilter === 'aws'} onClick={() => setProviderFilter('aws')} />
              <FilterChip label="GCP" count={counts.gcp} active={providerFilter === 'gcp'} onClick={() => setProviderFilter('gcp')} />
              <FilterChip label="Healthy" count={counts.healthy} active={healthFilter === 'healthy'} onClick={() => setHealthFilter('healthy')} />
              <FilterChip label="Needs Attention" count={counts.attention} active={healthFilter === 'attention'} onClick={() => setHealthFilter('attention')} />
              <button
                onClick={() => {
                  loadBindings()
                  loadIntegrations()
                }}
                disabled={loading || integrationsLoading}
                style={{
                  marginLeft: 'auto', padding: '6px 12px', borderRadius: 8, fontSize: 12,
                  border: '1px solid var(--border)', background: 'var(--bg-card)',
                  color: 'var(--text-muted)', cursor: loading ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                }}
              >
                <RefreshCw size={12} style={{ animation: loading || integrationsLoading ? 'spin 1s linear infinite' : 'none' }} />
                Refresh
              </button>
            </div>
          </div>

          <div style={{ padding: 18 }}>
            {/* Error */}
            {error && (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#ef4444', display: 'flex', gap: 8, marginBottom: 16 }}>
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                {error}
              </div>
            )}

            {loading ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
                <Loader size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
                <p style={{ fontSize: 13 }}>Loading cloud accounts…</p>
              </div>
            ) : filtered.length === 0 ? (
              <div style={{
                background: 'var(--bg-card)', border: '1px dashed var(--border)',
                borderRadius: 10, padding: '48px 24px', textAlign: 'center',
              }}>
                <Cloud size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display: 'block', opacity: 0.4 }} />
                <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>No cloud accounts in this view</p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Adjust filters or onboard an AWS account or GCP project to continue.
                </p>
                <button
                  onClick={() => setShowAdd(true)}
                  style={{
                    marginTop: 16, display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '8px 16px', borderRadius: 8, border: 'none',
                    background: 'var(--neon-cyan)', color: '#000',
                    fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  <Plus size={13} />
                  Onboard Account
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {filtered.map((binding) => (
                  <BindingCard
                    key={binding.id}
                    binding={binding}
                    integrations={integrations}
                    onDelete={handleDeleted}
                    onRotate={setRotatingBinding}
                    onSetDefault={handleSetDefault}
                    onLaunchIntegration={launchMonitoring}
                    tenantId={tenantId}
                  />
                ))}
              </div>
            )}
          </div>
        </section>

        <section style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-card)', padding: 18 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Zone B
            </div>
            <h3 style={{ margin: '6px 0 0', fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>
              Monitoring Actions
            </h3>
            <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Native monitoring is account-level. Datadog, Grafana, Prometheus, and webhook sources are tenant-level integrations.
            </p>
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-card)', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Account-Level Monitoring
            </div>
            <ActionRow
              title="CloudWatch"
              subtitle="Connect native AWS alarms for onboarded AWS accounts."
              statusLabel={integrationsLoading ? 'Checking' : hasActiveIntegration('cloudwatch') ? 'Configured' : 'Coming Soon'}
              statusTone={integrationsLoading ? 'muted' : hasActiveIntegration('cloudwatch') ? 'healthy' : 'muted'}
              actionLabel={hasActiveIntegration('cloudwatch') ? 'Manage' : 'Unavailable'}
              onAction={() => launchMonitoring('cloudwatch')}
              disabled={!hasActiveIntegration('cloudwatch') && !isAvailableIntegration('cloudwatch')}
            />
            <ActionRow
              title="GCP Monitoring"
              subtitle="Connect Google Cloud Monitoring for onboarded GCP projects."
              statusLabel={integrationsLoading ? 'Checking' : hasActiveIntegration('gcp_monitoring') ? 'Configured' : 'Coming Soon'}
              statusTone={integrationsLoading ? 'muted' : hasActiveIntegration('gcp_monitoring') ? 'healthy' : 'muted'}
              actionLabel={hasActiveIntegration('gcp_monitoring') ? 'Manage' : 'Unavailable'}
              onAction={() => launchMonitoring('gcp_monitoring')}
              disabled={!hasActiveIntegration('gcp_monitoring') && !isAvailableIntegration('gcp_monitoring')}
            />
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-card)', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Workspace-Level Integrations
            </div>
            <ActionRow
              title="Datadog"
              subtitle="Route Datadog monitors and incidents into AIREX workflows."
              statusLabel={hasActiveIntegration('datadog') ? 'Configured' : 'Coming Soon'}
              statusTone={hasActiveIntegration('datadog') ? 'healthy' : 'muted'}
              actionLabel={hasActiveIntegration('datadog') ? 'Manage' : 'Unavailable'}
              onAction={() => launchMonitoring('datadog')}
              disabled={!hasActiveIntegration('datadog') && !isAvailableIntegration('datadog')}
            />
            <ActionRow
              title="Grafana"
              subtitle="Connect Grafana alerting for workspace-wide dashboards and services."
              statusLabel={hasActiveIntegration('grafana') ? 'Configured' : 'Coming Soon'}
              statusTone={hasActiveIntegration('grafana') ? 'healthy' : 'muted'}
              actionLabel={hasActiveIntegration('grafana') ? 'Manage' : 'Unavailable'}
              onAction={() => launchMonitoring('grafana')}
              disabled={!hasActiveIntegration('grafana') && !isAvailableIntegration('grafana')}
            />
            <ActionRow
              title="Prometheus"
              subtitle="Use Prometheus or Alertmanager webhooks as a tenant-level alert source."
              statusLabel={hasActiveIntegration('prometheus') ? 'Configured' : 'Coming Soon'}
              statusTone={hasActiveIntegration('prometheus') ? 'healthy' : 'muted'}
              actionLabel={hasActiveIntegration('prometheus') ? 'Manage' : 'Unavailable'}
              onAction={() => launchMonitoring('prometheus')}
              disabled={!hasActiveIntegration('prometheus') && !isAvailableIntegration('prometheus')}
            />
            <ActionRow
              title="Custom Webhook"
              subtitle="Accept alerts from sources that can push webhooks into AIREX."
              statusLabel={hasActiveIntegration('custom_webhook') ? 'Configured' : 'Coming Soon'}
              statusTone={hasActiveIntegration('custom_webhook') ? 'healthy' : 'muted'}
              actionLabel={hasActiveIntegration('custom_webhook') ? 'Manage' : 'Unavailable'}
              onAction={() => launchMonitoring('custom_webhook')}
              disabled={!hasActiveIntegration('custom_webhook') && !isAvailableIntegration('custom_webhook')}
            />
          </div>

          <SummaryCard
            label="Next Step Guidance"
            value={counts.attention > 0 ? String(counts.attention) : '0'}
            hint={counts.attention > 0
              ? 'Some accounts still need native monitoring or tenant-level alert sources. Move next into monitoring and then workflows.'
              : 'All visible accounts have the required identity metadata. Keep monitoring and routing current from the integrations page.'}
            tone={counts.attention > 0 ? 'attention' : 'healthy'}
            action={(
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-start' }}>
                <button
                  type="button"
                  onClick={() => launchMonitoring('cloudwatch')}
                  style={{
                    padding: '7px 10px',
                    borderRadius: 8,
                    border: '1px solid rgba(34,211,238,0.28)',
                    background: 'rgba(34,211,238,0.08)',
                    color: 'var(--neon-cyan)',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Connect Native Monitoring
                </button>
                <button
                  type="button"
                  onClick={() => launchMonitoring('datadog')}
                  style={{
                    padding: '7px 10px',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-elevated)',
                    color: 'var(--text-secondary)',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Add Datadog
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/runbooks')}
                  style={{
                    padding: '7px 10px',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'var(--bg-elevated)',
                    color: 'var(--text-secondary)',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Create Alert Workflow
                </button>
              </div>
            )}
          />
        </section>
      </div>

      {/* Info box */}
      <div style={{
        background: 'rgba(34,211,238,0.05)', border: '1px solid rgba(34,211,238,0.2)',
        borderRadius: 8, padding: '12px 16px', fontSize: 12, color: 'var(--text-muted)',
        display: 'flex', gap: 8,
      }}>
        <Shield size={14} style={{ color: 'var(--neon-cyan)', flexShrink: 0, marginTop: 1 }} />
        <span>
          Credentials are never stored in the database. Static keys are encrypted in{' '}
          <strong style={{ color: 'var(--text-secondary)' }}>AWS Secrets Manager</strong>{' '}
          under <code style={{ fontFamily: 'monospace' }}>{'{prefix}/tenant/{id}/{provider}/{binding-id}'}</code>.
          For production workloads, prefer cross-account IAM role assumption (no stored keys needed).
        </span>
      </div>

      {/* Modals */}
      {showAdd && (
        <AddBindingModal
          onClose={() => setShowAdd(false)}
          onCreated={handleCreated}
          onLaunchIntegration={onLaunchIntegration}
          tenantId={tenantId}
        />
      )}
      {rotatingBinding && (
        <RotateCredentialsModal
          binding={rotatingBinding}
          onClose={() => setRotatingBinding(null)}
          onRotated={handleRotated}
          tenantId={tenantId}
        />
      )}
    </div>
  )
}
