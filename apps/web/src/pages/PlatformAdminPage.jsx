import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRightCircle,
  Brain,
  Building2,
  CheckCircle,
  ChevronRight,
  Globe,
  Layers,
  LogOut,
  Plus,
  RefreshCcw,
  Settings,
  ShieldCheck,
  Trash2,
  Users,
  X,
  XCircle,
  Zap,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useToasts } from '../context/ToastContext'
import TenantWorkspaceManager from '../components/admin/TenantWorkspaceManager'
import {
  createOrganization,
  fetchBackendHealth,
  fetchDLQ,
  fetchMetrics,
  fetchOrganizations,
  fetchSettings,
  fetchTenants,
  fetchUsers,
  replayDLQEntry,
  clearDLQ,
} from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'
import { formatRelativeTime } from '../utils/formatters'
import { FALLBACK_TENANT_ID } from '../utils/constants'

// ── Helpers ───────────────────────────────────────────────────────────────────

function useToast() {
  const { addToast } = useToasts()
  return useCallback(
    (msg, type = 'success') =>
      addToast({
        title: type === 'error' ? 'Error' : 'Success',
        message: msg,
        severity: type === 'error' ? 'CRITICAL' : 'LOW',
      }),
    [addToast]
  )
}

const inputCls = {
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13,
  outline: 'none',
  width: '100%',
}

function StatCard({ label, value, color = 'var(--neon-indigo)', icon: Icon, sub }) {
  return (
    <div className="glass rounded-xl p-4 flex flex-col gap-1" style={{ border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        {Icon && <Icon size={14} style={{ color, opacity: 0.7 }} />}
      </div>
      <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
      {sub && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sub}</span>}
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>
      {children}
    </p>
  )
}

function StatusBadge({ status }) {
  const map = {
    active:    { bg: 'rgba(34,197,94,0.12)',   color: 'var(--color-accent-green)', label: 'Active' },
    disabled:  { bg: 'rgba(148,163,184,0.12)', color: 'var(--text-muted)',         label: 'Disabled' },
    suspended: { bg: 'rgba(244,63,94,0.12)',   color: 'var(--color-accent-red)',   label: 'Suspended' },
  }
  const s = map[status] || map.disabled
  return (
    <span style={{ fontSize: 10, fontWeight: 700, background: s.bg, color: s.color, borderRadius: 999, padding: '3px 9px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {s.label}
    </span>
  )
}

// ── Nav sections ──────────────────────────────────────────────────────────────

const SECTIONS = [
  { id: 'overview',      label: 'Overview',       icon: Activity },
  { id: 'organizations', label: 'Organizations',  icon: Globe },
  { id: 'workspaces',    label: 'Workspaces',     icon: Layers },
  { id: 'integrations',  label: 'Integrations',   icon: Zap },
  { id: 'settings',      label: 'Settings',       icon: Settings },
]

// ── Overview Section ──────────────────────────────────────────────────────────

function OverviewSection({ onNavigate }) {
  const { user, tenants: authTenants } = useAuth()
  const [health,  setHealth]  = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [users,   setUsers]   = useState([])
  const [tenants, setTenants] = useState([])
  const [orgs,    setOrgs]    = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchBackendHealth().catch(() => null),
      fetchMetrics().catch(() => null),
      fetchUsers({ limit: 100 }).catch(() => ({ items: [] })),
      fetchTenants().catch(() => []),
      fetchOrganizations().catch(() => []),
    ]).then(([h, m, u, t, o]) => {
      setHealth(h)
      setMetrics(m)
      setUsers(u?.items || [])
      setTenants(Array.isArray(t) ? t : [])
      setOrgs(Array.isArray(o) ? o : [])
    }).finally(() => setLoading(false))
  }, [])

  const STATUS_ROWS = [
    { label: 'Backend API',   ok: health?.status === 'ok', detail: 'FastAPI + Uvicorn' },
    { label: 'Database',      ok: true,                     detail: 'PostgreSQL 15 + RLS' },
    { label: 'Redis / Queue', ok: true,                     detail: 'ARQ Worker' },
    { label: 'AI Engine',     ok: true,                     detail: 'Gemini 2.0 Flash' },
  ]

  return (
    <div className="space-y-6">
      {/* Health */}
      <div>
        <SectionTitle>System Health</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {STATUS_ROWS.map(s => (
            <div key={s.label} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              {loading
                ? <div className="w-4 h-4 rounded-full animate-pulse" style={{ background: 'var(--border)' }} />
                : s.ok
                  ? <CheckCircle size={16} style={{ color: 'var(--neon-green)', flexShrink: 0 }} />
                  : <AlertTriangle size={16} style={{ color: 'var(--brand-orange)', flexShrink: 0 }} />
              }
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{s.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Users"        value={loading ? '…' : users.length}                              color="var(--neon-indigo)"  icon={Users}         sub={`${users.filter(u => u.is_active !== false).length} active`} />
        <StatCard label="Organizations" value={loading ? '…' : orgs.length}                             color="#22d3ee"             icon={Globe}         sub="Registered" />
        <StatCard label="Workspaces"   value={loading ? '…' : (tenants.length || authTenants?.length || '—')} color="var(--brand-orange)" icon={Layers}    sub="Tenant spaces" />
        <StatCard label="Active Alerts" value={loading ? '…' : (metrics?.active_alerts ?? '—')}         color="var(--brand-orange)" icon={AlertTriangle} sub={`${metrics?.critical_alerts ?? 0} critical`} />
      </div>

      {/* Session info */}
      <div>
        <SectionTitle>Current Session</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: 'Tenant ID',   value: user?.tenantId || user?.tenant_id || FALLBACK_TENANT_ID, mono: true },
            { label: 'Logged in as', value: user?.email || '—',                                     mono: false },
            { label: 'Role',        value: (user?.role || '—').toUpperCase(),                       mono: true },
          ].map(item => (
            <div key={item.label} className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</div>
              <div style={{ fontFamily: item.mono ? 'var(--font-mono)' : 'inherit', fontSize: 12, color: 'var(--text-heading)', marginTop: 4, wordBreak: 'break-all' }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick nav */}
      <div>
        <SectionTitle>Quick Navigation</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {SECTIONS.filter(s => s.id !== 'overview').map(sec => (
            <button
              key={sec.id}
              onClick={() => onNavigate(sec.id)}
              className="glass rounded-xl p-4 flex items-center gap-3 hover-lift transition-all text-left"
              style={{ border: '1px solid var(--border)', cursor: 'pointer' }}
            >
              <div className="p-2 rounded-lg" style={{ background: 'rgba(99,102,241,0.12)' }}>
                <sec.icon size={15} style={{ color: 'var(--neon-indigo)' }} />
              </div>
              <div className="min-w-0">
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{sec.label}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {sec.id === 'organizations' && `${loading ? '…' : orgs.length} orgs`}
                  {sec.id === 'users'         && `${loading ? '…' : users.length} users`}
                  {sec.id === 'workspaces'    && 'Tenant workspace management'}
                  {sec.id === 'integrations'  && 'Monitor integrations'}
                  {sec.id === 'settings'      && 'System configuration'}
                </div>
              </div>
              <ChevronRight size={13} style={{ color: 'var(--text-muted)', marginLeft: 'auto', flexShrink: 0 }} />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Organizations Section ─────────────────────────────────────────────────────

function OrganizationsSection() {
  const { organizations: authOrgs, activeOrganization, tenants, switchTenant } = useAuth()

  const [remoteOrgs,  setRemoteOrgs]  = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [refreshing,  setRefreshing]  = useState(false)
  const [switching,   setSwitching]   = useState(null)
  const [showCreate,  setShowCreate]  = useState(false)

  const navigate = useNavigate()

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    try {
      const data = await fetchOrganizations()
      setRemoteOrgs(Array.isArray(data) ? data : null)
    } catch {
      setRemoteOrgs(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const orgList = remoteOrgs || authOrgs || []

  const isActiveOrg   = org => String(org.id) === String(activeOrganization?.id)
  const tenantCount   = org => {
    if (org.tenant_count != null) return org.tenant_count
    return tenants?.filter(t => String(t.organization_id) === String(org.id)).length ?? 0
  }

  const handleSwitch = async (org) => {
    const match = tenants?.find(t => String(t.organization_id) === String(org.id))
    if (!match) return
    setSwitching(org.id)
    try {
      await switchTenant(match.id)
      navigate('/dashboard', { replace: false })
    } finally {
      setSwitching(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>Organizations</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>Manage and switch between organizations you have access to.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
          >
            <RefreshCcw size={11} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white"
            style={{ background: 'var(--gradient-primary)' }}
          >
            <Plus size={11} />
            New Org
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Organizations"   value={loading ? '…' : orgList.length}           color="#22d3ee"             icon={Globe} />
        <StatCard label="Active Org"      value={activeOrganization?.name || '—'}           color="var(--neon-indigo)"  icon={CheckCircle} sub={activeOrganization?.slug} />
        <StatCard label="Tenant Spaces"   value={tenants?.length ?? '—'}                    color="var(--brand-orange)" icon={Layers} />
      </div>

      {/* Org list */}
      <div>
        <SectionTitle>All Organizations</SectionTitle>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="glass rounded-xl animate-pulse" style={{ border: '1px solid var(--border)', height: 76 }} />
            ))}
          </div>
        ) : orgList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 rounded-xl"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            <Building2 size={28} style={{ opacity: 0.3, marginBottom: 10 }} />
            <p style={{ fontSize: 13 }}>No organizations found</p>
          </div>
        ) : (
          <div className="space-y-2">
            {orgList.map(org => {
              const active    = isActiveOrg(org)
              const tCount    = tenantCount(org)
              const canSwitch = tenants?.some(t => String(t.organization_id) === String(org.id))

              return (
                <div
                  key={org.id}
                  className="glass rounded-xl p-4 flex items-center justify-between gap-4"
                  style={{
                    border: active ? '1px solid rgba(34,211,238,0.45)' : '1px solid var(--border)',
                    background: active ? 'rgba(34,211,238,0.04)' : undefined,
                  }}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className="flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0"
                      style={{ background: active ? 'rgba(34,211,238,0.12)' : 'var(--bg-input)', border: '1px solid var(--border)' }}
                    >
                      <Building2 size={16} style={{ color: active ? '#22d3ee' : 'var(--text-muted)' }} />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{org.name}</span>
                        {active && (
                          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full"
                            style={{ fontSize: 9, fontWeight: 700, background: 'rgba(34,211,238,0.12)', color: '#22d3ee', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            <CheckCircle size={8} /> Current
                          </span>
                        )}
                        {org.status && <StatusBadge status={org.status} />}
                      </div>
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 1 }}>{org.slug}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="hidden sm:flex items-center gap-1.5" style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      <Layers size={12} />
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{tCount}</span>
                      <span>tenant{tCount !== 1 ? 's' : ''}</span>
                    </div>
                    {active ? (
                      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
                        style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.25)', fontSize: 12, fontWeight: 600, color: '#22d3ee' }}>
                        <CheckCircle size={12} /> Active
                      </div>
                    ) : canSwitch ? (
                      <button
                        onClick={() => handleSwitch(org)}
                        disabled={switching === org.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover-lift"
                        style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', cursor: 'pointer', opacity: switching === org.id ? 0.6 : 1 }}
                      >
                        {switching === org.id ? <RefreshCcw size={12} className="animate-spin" /> : <ArrowRightCircle size={12} />}
                        Switch
                      </button>
                    ) : (
                      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
                        style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)', opacity: 0.5 }}>
                        <XCircle size={12} /> No tenants
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {showCreate && (
        <CreateOrgModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(true) }}
        />
      )}
    </div>
  )
}

function CreateOrgModal({ onClose, onCreated }) {
  const toast = useToast()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [saving, setSaving] = useState(false)

  const autoSlug = v => v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

  const handleNameChange = v => {
    setName(v)
    setSlug(autoSlug(v))
  }

  const handleSave = async () => {
    if (!name.trim() || !slug.trim()) { toast('Name and slug are required', 'error'); return }
    setSaving(true)
    try {
      await createOrganization({ name: name.trim(), slug: slug.trim() })
      toast('Organization created')
      onCreated()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Create failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div className="relative w-full max-w-md mx-4 glass rounded-2xl p-6 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>Create Organization</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Organization Name</label>
          <input value={name} onChange={e => handleNameChange(e.target.value)} placeholder="Acme Corp" style={inputCls} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug (URL-safe)</label>
          <input value={slug} onChange={e => setSlug(autoSlug(e.target.value))} placeholder="acme-corp" style={{ ...inputCls, fontFamily: 'var(--font-mono)', fontSize: 12 }} />
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Settings Section ──────────────────────────────────────────────────────────

function SettingsSection() {
  const toast = useToast()
  const [settings,  setSettings]  = useState(null)
  const [dlq,       setDlq]       = useState([])
  const [loading,   setLoading]   = useState(true)
  const [dlqLoading, setDlqLoading] = useState(false)
  const [replayingIdx, setReplayingIdx] = useState(null)
  const [clearing,  setClearing]  = useState(false)

  useEffect(() => {
    Promise.all([
      fetchSettings().catch(() => null),
      fetchDLQ({ limit: 50 }).catch(() => ({ items: [] })),
    ]).then(([s, d]) => {
      setSettings(s)
      setDlq(d?.items || [])
    }).finally(() => setLoading(false))
  }, [])

  const reloadDlq = async () => {
    setDlqLoading(true)
    try {
      const d = await fetchDLQ({ limit: 50 })
      setDlq(d?.items || [])
    } finally {
      setDlqLoading(false)
    }
  }

  const handleReplay = async (idx) => {
    setReplayingIdx(idx)
    try {
      await replayDLQEntry(idx)
      toast('Entry replayed')
      reloadDlq()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Replay failed', 'error')
    } finally {
      setReplayingIdx(null)
    }
  }

  const handleClearDlq = async () => {
    if (!window.confirm('Clear all DLQ entries? This cannot be undone.')) return
    setClearing(true)
    try {
      await clearDLQ()
      setDlq([])
      toast('DLQ cleared')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Clear failed', 'error')
    } finally {
      setClearing(false)
    }
  }

  const ConfigRow = ({ label, value, mono = false }) => (
    <div className="flex items-center justify-between py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontSize: 12, fontFamily: mono ? 'var(--font-mono)' : 'inherit', color: 'var(--text-heading)', fontWeight: 600, maxWidth: '55%', textAlign: 'right', wordBreak: 'break-all' }}>
        {value ?? '—'}
      </span>
    </div>
  )

  return (
    <div className="space-y-8">
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>Settings</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>Platform configuration, AI models, and pipeline tuning.</p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="glass rounded-xl h-20 skeleton" style={{ border: '1px solid var(--border)' }} />)}
        </div>
      ) : (
        <>
          {/* AI / LLM */}
          <div>
            <SectionTitle>AI Engine</SectionTitle>
            <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)' }}>
              <div className="flex items-center gap-2 mb-4">
                <Brain size={15} style={{ color: 'var(--neon-purple)' }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>LLM Configuration</span>
              </div>
              <ConfigRow label="Provider"         value={settings?.llm_provider}         mono />
              <ConfigRow label="Primary Model"    value={settings?.llm_primary_model}    mono />
              <ConfigRow label="Fallback Model"   value={settings?.llm_fallback_model}   mono />
              <ConfigRow label="Circuit Breaker Threshold" value={settings?.llm_circuit_breaker_threshold} />
              <ConfigRow label="Circuit Breaker Cooldown"  value={settings?.llm_circuit_breaker_cooldown != null ? `${settings.llm_circuit_breaker_cooldown}s` : null} />
            </div>
          </div>

          {/* Pipeline timeouts */}
          <div>
            <SectionTitle>Pipeline Timeouts &amp; Retries</SectionTitle>
            <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)' }}>
              <div className="flex items-center gap-2 mb-4">
                <Clock size={15} style={{ color: 'var(--neon-cyan)' }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Execution Limits</span>
              </div>
              <ConfigRow label="Investigation Timeout"  value={settings?.investigation_timeout  != null ? `${settings.investigation_timeout}s`  : null} />
              <ConfigRow label="Execution Timeout"      value={settings?.execution_timeout      != null ? `${settings.execution_timeout}s`      : null} />
              <ConfigRow label="Verification Timeout"   value={settings?.verification_timeout   != null ? `${settings.verification_timeout}s`   : null} />
              <ConfigRow label="Max Investigation Retries" value={settings?.max_investigation_retries} />
              <ConfigRow label="Max Execution Retries"     value={settings?.max_execution_retries} />
              <ConfigRow label="Max Verification Retries"  value={settings?.max_verification_retries} />
              <ConfigRow label="Redis Lock TTL"         value={settings?.lock_ttl != null ? `${settings.lock_ttl}s` : null} />
            </div>
          </div>

          {/* Notifications */}
          {(settings?.slack_webhook_url || settings?.email_smtp_host) && (
            <div>
              <SectionTitle>Notifications</SectionTitle>
              <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2 mb-4">
                  <Zap size={15} style={{ color: 'var(--neon-green)' }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Notification Channels</span>
                </div>
                {settings?.slack_webhook_url && (
                  <ConfigRow label="Slack Webhook" value="Configured" />
                )}
                {settings?.email_smtp_host && (
                  <>
                    <ConfigRow label="SMTP Host" value={settings.email_smtp_host} mono />
                    <ConfigRow label="SMTP Port" value={settings.email_smtp_port} />
                    <ConfigRow label="From Email" value={settings.email_from} />
                  </>
                )}
              </div>
            </div>
          )}

          {/* DLQ */}
          <div>
            <SectionTitle>Dead Letter Queue</SectionTitle>
            <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)' }}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={15} style={{ color: 'var(--brand-orange)' }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Failed Jobs</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, color: dlq.length > 0 ? 'var(--brand-orange)' : 'var(--neon-green)', background: dlq.length > 0 ? 'rgba(251,146,60,0.12)' : 'rgba(52,211,153,0.12)', borderRadius: 999, padding: '2px 8px' }}>
                    {dlq.length} entries
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={reloadDlq} disabled={dlqLoading} className="p-1.5 rounded" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                    <RefreshCcw size={12} style={{ color: 'var(--text-muted)' }} className={dlqLoading ? 'animate-spin' : ''} />
                  </button>
                  {dlq.length > 0 && (
                    <button onClick={handleClearDlq} disabled={clearing} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                      style={{ background: 'rgba(244,63,94,0.10)', border: '1px solid rgba(244,63,94,0.25)', color: 'var(--color-accent-red)' }}>
                      <Trash2 size={11} /> {clearing ? 'Clearing…' : 'Clear All'}
                    </button>
                  )}
                </div>
              </div>

              {dlq.length === 0 ? (
                <div className="flex items-center gap-2 py-4" style={{ color: 'var(--neon-green)' }}>
                  <CheckCircle size={14} />
                  <span style={{ fontSize: 13 }}>No failed jobs in queue</span>
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {dlq.map((entry, idx) => (
                    <div key={idx} className="flex items-center justify-between gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                      <div className="min-w-0">
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                          {entry.function || entry.job_id || `Entry #${idx}`}
                        </div>
                        {entry.error && (
                          <div style={{ fontSize: 11, color: 'var(--color-accent-red)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 400 }}>
                            {entry.error}
                          </div>
                        )}
                        {entry.enqueue_time && (
                          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{formatRelativeTime(entry.enqueue_time)}</div>
                        )}
                      </div>
                      <button
                        onClick={() => handleReplay(idx)}
                        disabled={replayingIdx === idx}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold flex-shrink-0"
                        style={{ background: 'var(--glow-indigo)', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--neon-indigo)' }}
                      >
                        {replayingIdx === idx ? <RefreshCcw size={11} className="animate-spin" /> : <ArrowRightCircle size={11} />}
                        Replay
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Page Shell ────────────────────────────────────────────────────────────────

export default function PlatformAdminPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const activeSection = searchParams.get('section') || 'overview'

  const setSection = useCallback((id) => {
    setSearchParams({ section: id }, { replace: true })
  }, [setSearchParams])

  const displayRole = (user?.role || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-base, #0f1117)', color: 'var(--text-primary, #e2e8f0)' }}>
      {/* Topbar */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b sticky top-0 z-40"
        style={{ background: 'var(--bg-surface, #1a1d27)', borderColor: 'var(--border, rgba(255,255,255,0.08))' }}
      >
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-sm font-semibold transition-opacity hover:opacity-70"
            style={{ color: 'var(--text-muted)' }}
          >
            <ArrowLeft size={15} />
            Dashboard
          </button>
          <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
          <div className="flex items-center gap-2">
            <Globe size={15} style={{ color: '#22d3ee' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>Platform Admin</span>
          </div>
          {user?.role && (
            <span
              className="px-2 py-0.5 rounded-full"
              style={{ fontSize: 10, fontWeight: 700, background: 'rgba(34,211,238,0.10)', color: '#22d3ee', border: '1px solid rgba(34,211,238,0.22)', textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              {displayRole}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <ShieldCheck size={12} style={{ color: 'var(--color-accent-green)' }} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>PLATFORM SCOPE</span>
          </div>
          {user?.display_name && (
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{user.display_name}</span>
          )}
          {logout && (
            <button
              onClick={() => { logout(); navigate('/login') }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-opacity hover:opacity-70"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
            >
              <LogOut size={12} />
              Sign out
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex min-h-[calc(100vh-49px)]">
        {/* Left nav */}
        <nav
          className="w-56 flex-shrink-0 border-r py-6 px-3 space-y-1"
          style={{ borderColor: 'var(--border)', background: 'var(--bg-surface, #1a1d27)' }}
        >
          {SECTIONS.map(sec => {
            const isActive = activeSection === sec.id
            return (
              <button
                key={sec.id}
                onClick={() => setSection(sec.id)}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all"
                style={{
                  background: isActive ? 'rgba(34,211,238,0.08)' : 'transparent',
                  border: isActive ? '1px solid rgba(34,211,238,0.20)' : '1px solid transparent',
                  color: isActive ? '#22d3ee' : 'var(--text-secondary)',
                  fontWeight: isActive ? 600 : 400,
                  fontSize: 13,
                }}
              >
                <sec.icon size={14} style={{ flexShrink: 0 }} />
                {sec.label}
              </button>
            )
          })}
        </nav>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="max-w-5xl mx-auto px-8 py-8 animate-fade-in">
            {activeSection === 'overview'      && <OverviewSection      onNavigate={setSection} />}
            {activeSection === 'organizations' && <OrganizationsSection />}
            {activeSection === 'workspaces'    && (
              <div className="space-y-4">
                <div>
                  <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>Workspaces</h2>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>Manage tenant workspaces, projects, and organization mappings.</p>
                </div>
                <TenantWorkspaceManager mode="organizations" />
              </div>
            )}
            {activeSection === 'integrations'  && (
              <div className="space-y-4">
                <div>
                  <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>Integrations</h2>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>Configure monitoring integrations, sync external monitors, and bind to projects.</p>
                </div>
                <TenantWorkspaceManager mode="integrations" />
              </div>
            )}
            {activeSection === 'settings'      && <SettingsSection />}
          </div>
        </main>
      </div>
    </div>
  )
}
