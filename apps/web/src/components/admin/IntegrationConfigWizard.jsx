import { useState } from 'react'
import { Check, Loader, X, AlertCircle, Zap, RefreshCw, Link2, Copy } from 'lucide-react'
import {
  createIntegration,
  updateIntegration,
  testIntegration,
  syncIntegrationMonitors,
  fetchExternalMonitors,
  createProjectMonitorBinding,
} from '../../services/api'

const STEPS = ['Setup', 'Test', 'Sync Monitors', 'Bind to Project', 'Done']

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
  onClose,
  onSaved,
}) {
  const isEdit = !!integration
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
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

  const configFields = integrationType.config_schema_json?.fields || []

  function setConfigField(key, value) {
    setForm((f) => ({ ...f, config: { ...f.config, [key]: value } }))
  }

  async function handleSetup() {
    if (!form.name.trim() || !form.slug.trim()) {
      setError('Name and slug are required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      let saved
      if (isEdit && savedIntegration) {
        saved = await updateIntegration(savedIntegration.id, {
          name: form.name,
          slug: form.slug,
          config_json: form.config,
          enabled: true,
        })
      } else {
        saved = await createIntegration(tenantId, {
          integration_type_id: integrationType.id,
          name: form.name,
          slug: form.slug,
          config_json: form.config,
          enabled: true,
        })
      }
      setSavedIntegration(saved)
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

  function handleDone() {
    onSaved?.()
    onClose()
  }

  const webhookUrl =
    savedIntegration?.webhook_path
      ? `${window.location.origin}${savedIntegration.webhook_path}`
      : null

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
      onClick={(e) => e.target === e.currentTarget && onClose()}
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
              Step {step + 1} of {STEPS.length} — {STEPS[step]}
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}>
            <X size={20} />
          </button>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-1 mb-8">
          {STEPS.map((label, i) => (
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
              {i < STEPS.length - 1 && (
                <div style={{ flex: 1, height: 2, background: i < step ? 'var(--neon-green)' : 'var(--border)', borderRadius: 1 }} />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        {step === 0 && (
          <div className="space-y-4">
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
              <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Cancel
              </button>
              <button
                onClick={handleSetup}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--neon-cyan)', color: '#000', border: 'none', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
              >
                {saving && <Loader size={14} className="animate-spin" />}
                Save & Continue
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
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

        {step === 2 && (
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

        {step === 3 && (
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

        {step === 4 && (
          <div className="space-y-5">
            <div className="flex flex-col items-center gap-3 py-4">
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(34,197,94,0.15)', border: '2px solid var(--neon-green)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Check size={24} style={{ color: 'var(--neon-green)' }} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>Integration Saved</h3>
              {bindResult && (
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
