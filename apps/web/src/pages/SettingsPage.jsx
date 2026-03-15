import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Settings, Server, Brain, Shield, Clock, Database,
  CheckCircle, AlertTriangle, RefreshCw, Save
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchBackendHealth, fetchSettings, updateSettings } from '../services/api'
import ConnectionBanner from '../components/common/ConnectionBanner'
import { FALLBACK_TENANT_ID } from '../utils/constants'
import { extractErrorMessage } from '../utils/errorHandler'

export default function SettingsPage() {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchHealth()
    if (user?.role === 'admin') {
      loadSettings()
    }
  }, [user])

  async function fetchHealth() {
    try {
      const data = await fetchBackendHealth()
      setHealth(data)
    } catch (err) {
      if (err?.response?.status === 404) {
        setHealth({ status: 'dev_backend_missing' })
        return
      }

      console.error('health check failed', err)
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  async function loadSettings() {
    try {
      const data = await fetchSettings()
      setSettings(data)
    } catch (err) {
      console.error('Failed to load settings:', err)
    }
  }

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    setError(null)
    try {
      await updateSettings(settings)
      alert('Settings updated. Note: Some settings require service restart to take effect.')
    } catch (err) {
      setError(extractErrorMessage(err) || err.message)
    } finally {
      setSaving(false)
    }
  }

  const configs = [
    {
      section: 'AI / LLM',
      icon: Brain,
      color: 'var(--neon-purple)',
      glassClass: 'glass-purple',
      items: [
        { label: 'Provider', value: settings?.llm_provider || '—' },
        { label: 'Primary Model', value: settings?.llm_primary_model || '—' },
        { label: 'Fallback Model', value: settings?.llm_fallback_model || '—' },
        {
          label: 'Circuit Breaker',
          value: settings
            ? `${settings.llm_circuit_breaker_threshold} failures / ${settings.llm_circuit_breaker_cooldown}s cooldown`
            : '—',
        },
      ],
    },
    {
      section: 'Pipeline',
      icon: RefreshCw,
      color: 'var(--neon-cyan)',
      glassClass: 'glass-cyan',
      items: [
        { label: 'Investigation Timeout', value: settings ? `${settings.investigation_timeout}s` : '—' },
        { label: 'Execution Timeout', value: settings ? `${settings.execution_timeout}s` : '—' },
        { label: 'Verification Timeout', value: settings ? `${settings.verification_timeout}s` : '—' },
        { label: 'Max Investigation Retries', value: settings ? String(settings.max_investigation_retries) : '—' },
        { label: 'Max Execution Retries', value: settings ? String(settings.max_execution_retries) : '—' },
        { label: 'Max Verification Retries', value: settings ? String(settings.max_verification_retries) : '—' },
        { label: 'Lock TTL', value: settings ? `${settings.lock_ttl}s` : '—' },
      ],
    },
    {
      section: 'Notifications',
      icon: Shield,
      color: 'var(--color-accent-amber)',
      glassClass: 'glass-amber',
      items: [
        { label: 'Slack Webhook', value: settings?.slack_webhook_url ? 'Configured' : 'Not set' },
        { label: 'SMTP Host', value: settings?.email_smtp_host || 'Not set' },
        { label: 'SMTP Port', value: settings?.email_smtp_port ? String(settings.email_smtp_port) : 'Not set' },
        { label: 'Email From', value: settings?.email_from || 'Not set' },
      ],
    },
    {
      section: 'Infrastructure',
      icon: Server,
      color: 'var(--neon-green)',
      glassClass: 'glass-green',
      items: [
        {
          label: 'Backend',
          value:
            health?.status === 'ok'
              ? 'Healthy'
              : health?.status === 'dev_backend_missing'
                ? 'Backend not running (Dev Mode)'
                : 'Unknown',
        },
        { label: 'Tenant ID', value: (user?.tenantId || user?.tenant_id || FALLBACK_TENANT_ID).slice(0, 8) + '...' },
        { label: 'Database', value: 'PostgreSQL' },
        { label: 'Queue', value: 'Redis + ARQ' },
        { label: 'SSE', value: 'Enabled' },
      ],
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
          <Settings size={24} style={{ color: 'var(--text-muted)' }} />
          Settings
        </h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          System configuration and status overview.
        </p>
      </div>

      {/* System Status */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>System Status</span>
          <button
            onClick={fetchHealth}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all"
            style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', background: 'var(--glow-indigo)', border: '1px solid rgba(99,102,241,0.2)' }}
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Backend API',
              ok: health?.status === 'ok',
              detail:
                health?.status === 'dev_backend_missing'
                  ? 'Backend not running (Dev Mode)'
                  : 'FastAPI + Uvicorn',
            },
            { label: 'Database', ok: true, detail: 'PostgreSQL + Alembic' },
            { label: 'Redis / Queue', ok: true, detail: 'ARQ Worker' },
            { label: 'AI Engine', ok: true, detail: 'Gemini 2.0 Flash' },
          ].map(s => (
            <div key={s.label} className="flex items-center gap-3 p-3 rounded-lg hover-lift" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              {s.ok ? (
                <CheckCircle size={18} style={{ color: 'var(--neon-green)', flexShrink: 0 }} />
              ) : loading ? (
                <RefreshCw size={18} style={{ color: 'var(--text-muted)', flexShrink: 0, animation: 'spin 1s linear infinite' }} />
              ) : (
                <AlertTriangle size={18} style={{ color: 'var(--brand-orange)', flexShrink: 0 }} />
              )}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{s.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid var(--color-accent-red)', background: 'var(--glow-rose-subtle)', fontSize: 14, color: 'var(--color-accent-red)' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {/* Config Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {configs.map(section => (
          <div key={section.section} className={`glass rounded-xl p-5 ${section.glassClass}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-1.5 rounded-lg" style={{ background: `${section.color}22` }}>
                <section.icon size={16} style={{ color: section.color }} />
              </div>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{section.section}</span>
            </div>
            <div className="space-y-2">
              {section.items.map(item => (
                <div key={item.label} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.label}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: 'var(--text-heading)' }}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {user?.role === 'admin' && settings && (
        <div className="glass rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Settings Management</span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all disabled:opacity-50 hover:shadow-lg hover:-translate-y-0.5 glow-indigo"
              style={{ fontSize: 12, fontWeight: 600, color: '#fff', background: 'var(--gradient-primary)' }}
            >
              <Save size={14} />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Note: Most settings are environment variables and require service restart to take effect.
          </p>

          <div
            className="mt-4 p-4 rounded-lg"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
                  Users & Roles
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  Add users, assign roles, and manage account status.
                </p>
              </div>
              <Link
                to="/admin/users"
                className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all hover:shadow-lg hover:-translate-y-0.5"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#fff',
                  background: 'linear-gradient(135deg, #0ea5e9, #2563eb)',
                }}
              >
                Open User Management
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Tenant Info */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Database size={16} style={{ color: 'var(--neon-indigo)' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Current Session</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tenant ID</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-heading)', marginTop: 4, wordBreak: 'break-all' }}>{user?.tenantId || user?.tenant_id || FALLBACK_TENANT_ID}</div>
          </div>
          <div className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mode</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-accent-amber)', marginTop: 4 }}>{user ? 'Authenticated' : 'Anonymous'}</div>
          </div>
          <div className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Version</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-heading)', marginTop: 4 }}>AIREX v0.9.0</div>
          </div>
        </div>
      </div>
    </div>
  )
}
