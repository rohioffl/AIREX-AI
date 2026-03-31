import { useState } from 'react'
import { Check, Loader, X, AlertCircle, Zap, RefreshCw, Link2, Copy } from 'lucide-react'
import {
  createIntegration,
  deleteIntegration,
  fetchWebhookEvents,
  updateIntegration,
  testIntegration,
  syncIntegrationMonitors,
  fetchExternalMonitors,
  createProjectMonitorBinding,
} from '../../services/api'

const DEFAULT_STEPS = ['Setup', 'Test', 'Sync Monitors', 'Bind to Project', 'Done']
const SITE24X7_STEPS = ['Setup', 'Configure Webhook', 'Test Alert', 'Overview', 'Done']

function slugify(str) {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function ConfigField({ field, value, onChange }) {
  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    background: 'var(--bg-input)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text-primary)',
    fontSize: 13,
    outline: 'none',
  }
  if (field.type === 'secret') {
    return (
      <input
        type="password"
        autoComplete="new-password"
        placeholder={field.placeholder || field.label}
        value={value || ''}
        onChange={(e) => onChange(field.key, e.target.value)}
        style={inputStyle}
      />
    )
  }
  if (field.type === 'number') {
    return (
      <input
        type="number"
        placeholder={field.placeholder || field.label}
        value={value || ''}
        onChange={(e) => onChange(field.key, e.target.value)}
        style={inputStyle}
      />
    )
  }
  return (
    <input
      type="text"
      placeholder={field.placeholder || field.label}
      value={value || ''}
      onChange={(e) => onChange(field.key, e.target.value)}
      style={inputStyle}
    />
  )
}

export default function IntegrationConfigWizard({
  integrationType,
  integration,
  tenantId,
  projects,
  cloudAccounts = [],
  defaultCloudAccountBindingId = null,
  onClose,
  onSaved,
}) {
  const isEdit = !!integration
  const isSite24x7 = integrationType.key === 'site24x7'
  const steps = isSite24x7 ? SITE24X7_STEPS : DEFAULT_STEPS
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    cloudAccountBindingId:
      integration?.cloud_account_binding_id ||
      defaultCloudAccountBindingId ||
      cloudAccounts[0]?.id ||
      '',
    name: integration?.name || integrationType.display_name,
    slug: integration?.slug || slugify(integrationType.display_name),
    config: integration?.config_json || {},
  })
  const [savedIntegration, setSavedIntegration] = useState(integration || null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [monitors, setMonitors] = useState([])
  const [selectedMonitors, setSelectedMonitors] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState(projects?.[0]?.id || '')
  const [binding, setBinding] = useState(false)
  const [bindResult, setBindResult] = useState(null)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [copiedPayload, setCopiedPayload] = useState(false)
  const [draftCreated, setDraftCreated] = useState(false)
  const [checkingAlert, setCheckingAlert] = useState(false)
  const [testAlertResult, setTestAlertResult] = useState(null)

  const configFields = integrationType.config_schema_json?.fields || []

  function setConfigField(key, value) {
    setForm((f) => ({ ...f, config: { ...f.config, [key]: value } }))
  }

  function validateSetup() {
    if (!form.name.trim() || !form.slug.trim()) {
      setError('Name and slug are required.')
      return false
    }
    if (cloudAccounts.length > 0 && !form.cloudAccountBindingId) {
      setError('Choose a cloud account so this integration stays isolated to that account.')
      return false
    }
    setError(null)
    return true
  }

  async function persistIntegration() {
    let saved
    if (isEdit && savedIntegration) {
      saved = await updateIntegration(savedIntegration.id, {
        integration_type_id: savedIntegration.integration_type_id || integrationType.id,
        cloud_account_binding_id: form.cloudAccountBindingId || null,
        name: form.name,
        slug: form.slug,
        config_json: form.config,
        enabled: true,
      })
    } else {
      saved = await createIntegration(tenantId, {
        integration_type_id: integrationType.id,
        cloud_account_binding_id: form.cloudAccountBindingId || null,
        name: form.name,
        slug: form.slug,
        config_json: form.config,
        enabled: true,
      })
    }
    setSavedIntegration(saved)
    return saved
  }

  async function ensureSite24x7Draft() {
    if (savedIntegration?.id) return savedIntegration
    const draft = await createIntegration(tenantId, {
      integration_type_id: integrationType.id,
      cloud_account_binding_id: form.cloudAccountBindingId || null,
      name: form.name,
      slug: form.slug,
      config_json: form.config,
      enabled: false,
      status: 'draft',
    })
    setSavedIntegration(draft)
    setDraftCreated(true)
    return draft
  }

  async function handleSetup() {
    if (!validateSetup()) return
    if (isSite24x7) {
      setSaving(true)
      try {
        if (!isEdit) {
          await ensureSite24x7Draft()
        }
        setStep(1)
      } catch (err) {
        setError(err?.response?.data?.detail || 'Failed to prepare webhook URL.')
      } finally {
        setSaving(false)
      }
      return
    }
    setSaving(true)
    try {
      await persistIntegration()
      setStep(1)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to save integration.')
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    if (!savedIntegration) return
    setTesting(true)
    setTestResult(null)
    setError(null)
    try {
      const result = await testIntegration(savedIntegration.id)
      setTestResult({ ok: true, message: result?.message || 'Connection verified.' })
    } catch (err) {
      setTestResult({
        ok: false,
        message: err?.response?.data?.detail || 'Connection test failed.',
      })
    } finally {
      setTesting(false)
    }
  }

  async function handleSync() {
    if (!savedIntegration) return
    setSyncing(true)
    setError(null)
    try {
      await syncIntegrationMonitors(savedIntegration.id)
      const fetched = await fetchExternalMonitors(savedIntegration.id)
      setMonitors(fetched || [])
      setSelectedMonitors((fetched || []).map((m) => m.id))
    } catch (err) {
      setError(err?.response?.data?.detail || 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  async function handleBind() {
    if (!savedIntegration || !selectedProjectId || selectedMonitors.length === 0) return
    setBinding(true)
    setError(null)
    const results = { ok: 0, failed: 0 }
    for (const monitorId of selectedMonitors) {
      try {
        await createProjectMonitorBinding(selectedProjectId, {
          external_monitor_id: monitorId,
          enabled: true,
        })
        results.ok++
      } catch {
        results.failed++
      }
    }
    setBindResult(results)
    setBinding(false)
    setStep(4)
  }

  function handleCopyWebhook() {
    const url = savedIntegration?.webhook_path
      ? `${window.location.origin}${savedIntegration.webhook_path}`
      : ''
    if (url) {
      navigator.clipboard.writeText(url).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  function handleCopyPayload() {
    if (site24x7PayloadExample) {
      navigator.clipboard.writeText(site24x7PayloadExample).catch(() => {})
      setCopiedPayload(true)
      setTimeout(() => setCopiedPayload(false), 2000)
    }
  }

  async function handleCheckTestAlert() {
    if (!savedIntegration?.id) return
    setCheckingAlert(true)
    setError(null)
    setTestAlertResult(null)
    try {
      const events = await fetchWebhookEvents(savedIntegration.id, 10)
      if (events?.length) {
        const latest = events[0]
        setTestAlertResult({
          ok: true,
          message: `Received ${latest.event_type || 'site24x7'} webhook at ${latest.received_at}.`,
        })
      } else {
        setTestAlertResult({
          ok: false,
          message: 'No webhook event received yet. Send a test alert from Site24x7, then check again.',
        })
      }
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to check webhook events.')
    } finally {
      setCheckingAlert(false)
    }
  }

  async function handleSite24x7Confirm() {
    if (!validateSetup()) return
    setSaving(true)
    try {
      let saved
      if (savedIntegration?.id) {
        saved = await updateIntegration(savedIntegration.id, {
          integration_type_id: savedIntegration.integration_type_id || integrationType.id,
          cloud_account_binding_id: form.cloudAccountBindingId || null,
          name: form.name,
          slug: form.slug,
          config_json: form.config,
          enabled: true,
          status: 'configured',
        })
      } else {
        saved = await persistIntegration()
      }
      setSavedIntegration(saved)
      setDraftCreated(false)
      setStep(4)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to save integration.')
    } finally {
      setSaving(false)
    }
  }

  async function handleClose() {
    if (isSite24x7 && draftCreated && savedIntegration?.id) {
      try {
        await deleteIntegration(savedIntegration.id)
      } catch {
        // Best-effort cleanup for abandoned drafts.
      }
    }
    onClose()
  }

  function handleDone() {
    onSaved?.()
    onClose()
  }

  const webhookUrl =
    savedIntegration?.webhook_path
      ? `${window.location.origin}${savedIntegration.webhook_path}`
      : null
  const site24x7PayloadExample = JSON.stringify(
    {
      MONITORNAME: '$MONITORNAME',
      INCIDENT_TIME_ISO: '$INCIDENT_TIME_ISO',
      MONITOR_DASHBOARD_LINK: '$MONITOR_DASHBOARD_LINK',
      STATUS: '$STATUS',
      INCIDENT_REASON: '$INCIDENT_REASON',
      MONITORURL: '$MONITORURL',
      MONITORID: '$MONITORID',
      MONITORTYPE: '$MONITORTYPE',
      TAGS: '$TAGS',
    },
    null,
    2
  )

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(4px)',
        padding: 16,
      }}
      onClick={(e) => e.target === e.currentTarget && handleClose()}
    >
      <div
        className="glass rounded-2xl"
        style={{ width: '100%', maxWidth: 560, maxHeight: '90vh', overflow: 'auto', padding: 32 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>
              {isEdit ? `Edit ${integrationType.display_name}` : `Connect ${integrationType.display_name}`}
            </h2>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 3 }}>
              Step {step + 1} of {steps.length} — {steps[step]}
            </p>
          </div>
          <button onClick={handleClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}>
            <X size={20} />
          </button>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-1 mb-8">
          {steps.map((label, i) => (
            <div key={label} className="flex items-center gap-1" style={{ flex: 1 }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11,
                  fontWeight: 700,
                  flexShrink: 0,
                  background: i < step ? 'var(--neon-green)' : i === step ? 'var(--neon-cyan)' : 'var(--bg-input)',
                  color: i <= step ? '#000' : 'var(--text-muted)',
                }}
              >
                {i < step ? <Check size={12} /> : i + 1}
              </div>
              {i < steps.length - 1 && (
                <div style={{ flex: 1, height: 2, background: i < step ? 'var(--neon-green)' : 'var(--border)', borderRadius: 1 }} />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        {step === 0 && (
          <div className="space-y-4">
            {cloudAccounts.length > 0 && (
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                  Cloud Account *
                </label>
                <select
                  value={form.cloudAccountBindingId}
                  onChange={(e) => setForm((f) => ({ ...f, cloudAccountBindingId: e.target.value }))}
                  style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                >
                  <option value="">Select cloud account</option>
                  {cloudAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.display_name || account.external_account_id || account.id}
                    </option>
                  ))}
                </select>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                  Each integration is tied to one tenant account so routing and monitor sync stay isolated.
                </p>
              </div>
            )}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Integration Name *
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value, slug: slugify(e.target.value) }))}
                style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                Slug <span style={{ fontWeight: 400 }}>(used in webhook paths)</span>
              </label>
              <input
                type="text"
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: 'monospace' }}
              />
            </div>
            {configFields.map((field) => (
              <div key={field.key}>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                  {field.label}{field.required && ' *'}
                </label>
                <ConfigField field={field} value={form.config[field.key]} onChange={setConfigField} />
              </div>
            ))}
            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={handleClose} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Cancel
              </button>
              <button
                onClick={handleSetup}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
              >
                {saving && <Loader size={14} className="animate-spin" />}
                {isSite24x7 ? 'Continue' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}

        {step === 1 && !isSite24x7 && (
          <div className="space-y-4">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Test the connection to verify credentials and network access.
            </p>
            {testResult && (
              <div
                className="flex items-start gap-3 rounded-xl p-4"
                style={{
                  background: testResult.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                  border: `1px solid ${testResult.ok ? 'var(--neon-green)' : 'rgba(239,68,68,0.4)'}`,
                }}
              >
                {testResult.ok ? <Check size={16} style={{ color: 'var(--neon-green)', flexShrink: 0, marginTop: 1 }} /> : <AlertCircle size={16} style={{ color: '#ef4444', flexShrink: 0, marginTop: 1 }} />}
                <p style={{ fontSize: 13, color: testResult.ok ? 'var(--neon-green)' : '#ef4444' }}>{testResult.message}</p>
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}
            <div className="flex justify-between mt-6">
              <button onClick={() => setStep(0)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Back
              </button>
              <div className="flex gap-3">
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--neon-cyan)', color: 'var(--neon-cyan)', cursor: testing ? 'not-allowed' : 'pointer', opacity: testing ? 0.7 : 1 }}
                >
                  {testing ? <Loader size={14} className="animate-spin" /> : <Zap size={14} />}
                  Test Connection
                </button>
                <button
                  onClick={() => setStep(2)}
                  className="px-4 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: 'pointer' }}
                >
                  {testResult?.ok ? 'Continue' : 'Skip'}
                </button>
              </div>
            </div>
          </div>
        )}

        {step === 1 && isSite24x7 && (
          <div className="space-y-5">
            <div
              className="rounded-xl p-4"
              style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.25)' }}
            >
              <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 8 }}>
                Configure this in Site24x7
              </p>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'grid', gap: 6 }}>
                <div>1. Go to <code>Admin -&gt; IT Automation -&gt; Webhooks</code> in Site24x7.</div>
                <div>2. Create a new webhook integration for this monitor or action rule.</div>
                <div>3. Set method to `POST`.</div>
                <div>4. Use the webhook URL below exactly as shown.</div>
                <div>5. Send a JSON payload with the monitor fields shown in the sample.</div>
              </div>
            </div>

            {webhookUrl ? (
              <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  Webhook URL
                </p>
                <div className="flex items-center gap-2">
                  <code style={{ flex: 1, fontSize: 11, color: 'var(--neon-cyan)', background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 10px', overflow: 'auto', whiteSpace: 'nowrap' }}>
                    {webhookUrl}
                  </code>
                  <button
                    onClick={handleCopyWebhook}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--neon-green)' : 'var(--text-secondary)', flexShrink: 0 }}
                    title="Copy webhook URL"
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </div>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                  This URL is already tenant-scoped and integration-scoped. No extra query parameter is required.
                </p>
              </div>
            ) : (
              <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  Webhook URL
                </p>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  The final webhook URL will be generated after you confirm the overview on the next step.
                </p>
              </div>
            )}

            <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div className="flex items-center justify-between gap-3 mb-3">
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Sample payload JSON
                </p>
                <button
                  onClick={handleCopyPayload}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: copiedPayload ? 'var(--neon-green)' : 'var(--text-secondary)', cursor: 'pointer' }}
                >
                  {copiedPayload ? <Check size={14} /> : <Copy size={14} />}
                  {copiedPayload ? 'Copied' : 'Copy JSON'}
                </button>
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: 12,
                  borderRadius: 10,
                  background: 'rgba(0,0,0,0.35)',
                  color: 'var(--neon-cyan)',
                  fontSize: 11,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {site24x7PayloadExample}
              </pre>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                AIREX accepts JSON and also tolerates form-encoded Site24x7 payloads, but JSON is the cleanest option.
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}

            <div className="flex justify-between mt-6">
              <button onClick={() => setStep(0)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Back
              </button>
              <button
                onClick={() => setStep(2)}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: 'pointer' }}
              >
                Review
              </button>
            </div>
          </div>
        )}

        {step === 2 && isSite24x7 && (
          <div className="space-y-5">
            <div
              className="rounded-xl p-4"
              style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.25)' }}
            >
              <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 8 }}>
                Test Alert
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Add the webhook in Site24x7, send a test alert, then click check below. AIREX will look for the latest webhook event for this integration.
              </p>
            </div>

            {webhookUrl && (
              <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  Webhook URL
                </p>
                <code style={{ display: 'block', fontSize: 11, color: 'var(--neon-cyan)', background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 10px', overflow: 'auto', whiteSpace: 'nowrap' }}>
                  {webhookUrl}
                </code>
              </div>
            )}

            {testAlertResult && (
              <div
                className="flex items-start gap-3 rounded-xl p-4"
                style={{
                  background: testAlertResult.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                  border: `1px solid ${testAlertResult.ok ? 'var(--neon-green)' : 'rgba(239,68,68,0.4)'}`,
                }}
              >
                {testAlertResult.ok ? <Check size={16} style={{ color: 'var(--neon-green)', flexShrink: 0, marginTop: 1 }} /> : <AlertCircle size={16} style={{ color: '#ef4444', flexShrink: 0, marginTop: 1 }} />}
                <p style={{ fontSize: 13, color: testAlertResult.ok ? 'var(--neon-green)' : '#ef4444' }}>{testAlertResult.message}</p>
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}

            <div className="flex justify-between mt-6">
              <button onClick={() => setStep(1)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Back
              </button>
              <div className="flex gap-3">
                <button
                  onClick={handleCheckTestAlert}
                  disabled={checkingAlert}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--neon-cyan)', color: 'var(--neon-cyan)', cursor: checkingAlert ? 'not-allowed' : 'pointer', opacity: checkingAlert ? 0.7 : 1 }}
                >
                  {checkingAlert ? <Loader size={14} className="animate-spin" /> : <Zap size={14} />}
                  Check Test Alert
                </button>
              <button
                onClick={() => setStep(3)}
                disabled={!testAlertResult?.ok}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{
                  background: 'var(--neon-cyan)',
                  color: '#000',
                  border: 'none',
                  cursor: testAlertResult?.ok ? 'pointer' : 'not-allowed',
                  opacity: testAlertResult?.ok ? 1 : 0.6,
                }}
              >
                Continue
              </button>
              </div>
            </div>
          </div>
        )}

        {step === 3 && isSite24x7 && (
          <div className="space-y-5">
            <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 12 }}>
                Overview
              </p>
              <div style={{ display: 'grid', gap: 10 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Cloud Account</div>
                  <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                    {cloudAccounts.find((account) => account.id === form.cloudAccountBindingId)?.display_name || 'Not selected'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Integration Name</div>
                  <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{form.name}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Slug</div>
                  <code style={{ fontSize: 12, color: 'var(--neon-cyan)' }}>{form.slug}</code>
                </div>
              </div>
            </div>

            <div
              className="rounded-xl p-4"
              style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.25)' }}
            >
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {isEdit
                  ? 'Changes are still local to this wizard. Confirm below to save them and refresh the live webhook details.'
                  : 'Nothing has been saved yet. Confirm below to create this integration and generate its live webhook URL.'}
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}

            <div className="flex justify-between mt-6">
              <button onClick={() => setStep(2)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Back
              </button>
              <button
                onClick={handleSite24x7Confirm}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
              >
                {saving && <Loader size={14} className="animate-spin" />}
                {isEdit ? 'Save Integration' : 'Create Integration'}
              </button>
            </div>
          </div>
        )}

        {step === 2 && !isSite24x7 && (
          <div className="space-y-4">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {integrationType.supports_sync
                ? 'Discover monitors from this integration to bind to projects.'
                : 'This integration type does not support automatic monitor sync.'}
            </p>
            {monitors.length > 0 && (
              <div style={{ maxHeight: 200, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {monitors.map((m) => (
                  <label key={m.id} className="flex items-center gap-3 rounded-lg p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selectedMonitors.includes(m.id)}
                      onChange={(e) =>
                        setSelectedMonitors((prev) =>
                          e.target.checked ? [...prev, m.id] : prev.filter((id) => id !== m.id)
                        )
                      }
                      style={{ accentColor: 'var(--neon-cyan)' }}
                    />
                    <div>
                      <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{m.external_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{m.monitor_type} · {m.status}</div>
                    </div>
                  </label>
                ))}
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}
            <div className="flex justify-between mt-6">
              <button onClick={() => setStep(1)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Back
              </button>
              <div className="flex gap-3">
                {integrationType.supports_sync && (
                  <button
                    onClick={handleSync}
                    disabled={syncing}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                    style={{ background: 'var(--bg-input)', border: '1px solid var(--neon-indigo)', color: 'var(--neon-indigo)', cursor: syncing ? 'not-allowed' : 'pointer', opacity: syncing ? 0.7 : 1 }}
                  >
                    {syncing ? <Loader size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    Sync Now
                  </button>
                )}
                <button
                  onClick={() => setStep(3)}
                  className="px-4 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: 'pointer' }}
                >
                  {monitors.length > 0 ? 'Continue' : 'Skip'}
                </button>
              </div>
            </div>
          </div>
        )}

        {step === 3 && !isSite24x7 && (
          <div className="space-y-4">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Bind selected monitors to a project to route alerts into incident workflows.
            </p>
            {projects?.length > 0 && monitors.length > 0 ? (
              <>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                    Target Project
                  </label>
                  <select
                    value={selectedProjectId}
                    onChange={(e) => setSelectedProjectId(e.target.value)}
                    className="px-3 py-2 rounded-lg border border-border bg-input text-text-primary"
                    style={{ fontSize: 13, width: '100%' }}
                  >
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                    Monitors to bind ({selectedMonitors.length} selected)
                  </label>
                  <div style={{ maxHeight: 180, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {monitors.map((m) => (
                      <label key={m.id} className="flex items-center gap-3 rounded-lg p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={selectedMonitors.includes(m.id)}
                          onChange={(e) =>
                            setSelectedMonitors((prev) =>
                              e.target.checked ? [...prev, m.id] : prev.filter((id) => id !== m.id)
                            )
                          }
                          style={{ accentColor: 'var(--neon-cyan)' }}
                        />
                        <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{m.external_name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-xl p-6 text-center" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)' }}>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {monitors.length === 0 ? 'No monitors discovered — sync first or skip.' : 'No projects available in this tenant.'}
                </p>
              </div>
            )}
            {error && (
              <div className="flex items-center gap-2" style={{ color: 'var(--neon-red)', fontSize: 13 }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}
            <div className="flex justify-between mt-6">
              <button onClick={() => setStep(2)} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Back
              </button>
              <div className="flex gap-3">
                {projects?.length > 0 && monitors.length > 0 && selectedMonitors.length > 0 && (
                  <button
                    onClick={handleBind}
                    disabled={binding}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                    style={{ background: 'var(--neon-indigo)', color: '#fff', border: 'none', cursor: binding ? 'not-allowed' : 'pointer', opacity: binding ? 0.7 : 1 }}
                  >
                    {binding ? <Loader size={14} className="animate-spin" /> : <Link2 size={14} />}
                    Bind Monitors
                  </button>
                )}
                <button
                  onClick={() => setStep(4)}
                  className="px-4 py-2 rounded-lg text-sm font-semibold"
                  style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: 'pointer' }}
                >
                  Skip
                </button>
              </div>
            </div>
          </div>
        )}

        {((isSite24x7 && step === 4) || (!isSite24x7 && step === 4)) && (
          <div className="space-y-5">
            <div className="flex flex-col items-center gap-3 py-4">
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(34,197,94,0.15)', border: '2px solid var(--neon-green)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Check size={24} style={{ color: 'var(--neon-green)' }} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>
                {isSite24x7 ? 'Webhook Ready' : 'Integration Saved'}
              </h3>
              {isSite24x7 && (
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center' }}>
                  Site24x7 is saved. Send a test webhook from Site24x7 to confirm alerts reach this tenant account.
                </p>
              )}
              {!isSite24x7 && bindResult && (
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center' }}>
                  Bound {bindResult.ok} monitor{bindResult.ok !== 1 ? 's' : ''}
                  {bindResult.failed > 0 ? ` (${bindResult.failed} failed)` : ''}.
                </p>
              )}
            </div>

            {webhookUrl && integrationType.supports_webhook && (
              <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  Webhook URL — paste this into {integrationType.display_name}
                </p>
                <div className="flex items-center gap-2">
                  <code style={{ flex: 1, fontSize: 11, color: 'var(--neon-cyan)', background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '6px 10px', overflow: 'auto', whiteSpace: 'nowrap' }}>
                    {webhookUrl}
                  </code>
                  <button
                    onClick={handleCopyWebhook}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--neon-green)' : 'var(--text-secondary)', flexShrink: 0 }}
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </div>
              </div>
            )}

            <div className="flex justify-end mt-4">
              <button
                onClick={handleDone}
                className="px-6 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: 'pointer' }}
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
