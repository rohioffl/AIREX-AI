import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  ArrowRightCircle,
  Brain,
  Building2,
  CheckCircle,
  ChevronRight,
  Clock,
  Edit,
  Globe,
  Layers,
  LogOut,
  Moon,
  Plus,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  Trash2,
  Users,
  X,
  XCircle,
  Zap,
} from 'lucide-react'

import TenantWorkspaceManager from '../components/admin/TenantWorkspaceManager'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { useToasts } from '../context/ToastContext'
import {
  clearDLQ,
  createPlatformAdmin,
  createIntegrationType,
  createOrganization,
  deleteIntegrationType,
  fetchBackendHealth,
  fetchDLQ,
  fetchIntegrationTypes,
  fetchOrganizations,
  fetchOrganizationTenants,
  fetchPlatformAnalytics,
  fetchPlatformAdmins,
  fetchSettings,
  replayDLQEntry,
  updateIntegrationType,
  updatePlatformAdmin,
  updateSettings,
} from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'
import { formatRelativeTime } from '../utils/formatters'

import './PlatformAdminPage.css'

function useToast() {
  const { addToast } = useToasts()
  return useCallback(
    (message, type = 'success') =>
      addToast({
        title: type === 'error' ? 'Error' : 'Success',
        message,
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

const textareaCls = {
  ...inputCls,
  minHeight: 112,
  fontFamily: 'var(--font-mono)',
  fontSize: 12,
}

function StatCard({ label, value, color = 'var(--neon-indigo)', icon: Icon, sub }) {
  return (
    <div
      className="glass pa-stat rounded-xl p-4 flex flex-col gap-1"
      style={{ border: '1px solid var(--border)', '--pa-stat-accent': color }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        {Icon && <Icon size={14} style={{ color, opacity: 0.75 }} />}
      </div>
      <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
      {sub && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sub}</span>}
    </div>
  )
}

function SectionTitle({ children }) {
  return <p className="pa-section-label">{children}</p>
}

function StatusBadge({ status }) {
  const meta = {
    active: { bg: 'rgba(34,197,94,0.12)', color: 'var(--color-accent-green)', label: 'Active' },
    disabled: { bg: 'rgba(148,163,184,0.12)', color: 'var(--text-muted)', label: 'Disabled' },
    suspended: { bg: 'rgba(244,63,94,0.12)', color: 'var(--color-accent-red)', label: 'Suspended' },
  }
  const current = meta[status] || meta.disabled
  return (
    <span style={{ fontSize: 10, fontWeight: 700, background: current.bg, color: current.color, borderRadius: 999, padding: '3px 9px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {current.label}
    </span>
  )
}

const SECTIONS = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'organizations', label: 'Organizations', icon: Globe },
  { id: 'workspaces', label: 'Workspaces', icon: Layers },
  { id: 'users', label: 'Users', icon: Users },
  { id: 'integrations', label: 'Integrations', icon: Zap },
  { id: 'settings', label: 'Settings', icon: Settings },
]

const SECTION_COPY = {
  overview: {
    title: 'Fleet overview',
    description:
      'Cross-workspace signals, capacity, and subsystem health. Use quick links to drill into organizations, workspaces, and global configuration.',
  },
  organizations: {
    title: 'Organizations',
    description:
      'Customer accounts and slugs. Map each organization to its workspaces and keep onboarding aligned with billing boundaries.',
  },
  workspaces: {
    title: 'Workspaces',
    description:
      'Workspace inventory, cloud bindings, and org mappings — without opening workspace-owned project data.',
  },
  users: {
    title: 'Platform admins',
    description:
      'Super-operator identities for this installation. Separate from workspace-scoped users in customer workspaces.',
  },
  integrations: {
    title: 'Integration catalog',
    description:
      'Global integration type definitions and schemas that workspaces instantiate for Site24x7, webhooks, and more.',
  },
  settings: {
    title: 'Platform settings',
    description:
      'Runtime flags, safety limits, and operational knobs that apply across the deployment.',
  },
}

function PageHero({ sectionId }) {
  const meta = SECTION_COPY[sectionId] || SECTION_COPY.overview
  const section = SECTIONS.find((s) => s.id === sectionId) || SECTIONS[0]
  const Icon = section.icon
  const isOverview = sectionId === 'overview'

  return (
    <div className={`pa-hero ${isOverview ? 'pa-hero--overview' : ''}`}>
      {!isOverview && (
        <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--neon-cyan)' }}>
          <Icon size={20} strokeWidth={2} />
        </div>
      )}
      {isOverview && (
        <p className="pa-kicker" style={{ marginBottom: 8, position: 'relative', zIndex: 1 }}>
          Platform control plane
        </p>
      )}
      <h1 className="pa-hero-title" style={{ position: 'relative', zIndex: 1 }}>
        {meta.title}
      </h1>
      <p className="pa-hero-desc" style={{ position: 'relative', zIndex: 1 }}>
        {meta.description}
      </p>
      {isOverview && (
        <div className="pa-hero-meta" style={{ position: 'relative', zIndex: 1 }}>
          <span className="pa-pulse">
            <span className="pa-pulse-dot" aria-hidden />
            Live stack monitoring
          </span>
          <span className="pa-hero-stat-pill">Multi-organization SaaS</span>
          <span className="pa-hero-stat-pill">RLS-isolated workspaces</span>
        </div>
      )}
    </div>
  )
}

function roleMeta(role) {
  const r = (role || 'operator').toLowerCase()
  if (r === 'platform_admin') return { label: 'PLATFORM ADMIN', color: '#d946ef', bg: 'rgba(217,70,239,0.12)' }
  if (r === 'admin')  return { label: 'ADMIN',    color: 'var(--neon-purple)', bg: 'rgba(192,132,252,0.12)' }
  if (r === 'viewer') return { label: 'VIEWER',   color: 'var(--text-muted)',  bg: 'rgba(148,163,184,0.12)' }
  return                     { label: 'OPERATOR', color: 'var(--neon-cyan)',   bg: 'rgba(56,189,248,0.12)' }
}

function PlatformAdminModal({ admin, onClose, onSaved, toast }) {
  const [form, setForm] = useState({
    email: admin?.email || '',
    display_name: admin?.display_name || '',
    password: '',
    is_active: admin?.is_active !== false,
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!form.email || !form.display_name) { toast('Email and name are required', 'error'); return }
    if (!admin && !form.password.trim()) { toast('Password is required for new platform admins', 'error'); return }
    setSaving(true)
    try {
      if (admin) {
        const payload = {
          display_name: form.display_name.trim(),
          is_active: form.is_active,
        }
        if (form.password.trim()) {
          payload.password = form.password
        }
        await updatePlatformAdmin(admin.id, payload)
        toast('Platform admin updated')
      } else {
        await createPlatformAdmin({
          email: form.email.trim(),
          display_name: form.display_name.trim(),
          password: form.password,
        })
        toast('Platform admin created')
      }
      onSaved()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div className="relative w-full max-w-md mx-4 glass rounded-2xl p-6 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>{admin ? 'Edit Platform Admin' : 'Create Platform Admin'}</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <input
          value={form.email}
          onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
          placeholder="Email address"
          type="email"
          disabled={Boolean(admin)}
          style={{ ...inputCls, opacity: admin ? 0.7 : 1 }}
        />
        <input value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} placeholder="Display name" style={inputCls} />
        <input
          value={form.password}
          onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
          placeholder={admin ? 'New password (optional)' : 'Password'}
          type="password"
          style={inputCls}
        />
        {admin && (
          <label className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-secondary)' }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
            />
            Account active
          </label>
        )}
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Saving…' : admin ? 'Save Changes' : 'Create Platform Admin'}
          </button>
        </div>
      </div>
    </div>
  )
}

function UsersSection() {
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [editingAdmin, setEditingAdmin] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchPlatformAdmins()
      setUsers((data.items || []).map((admin) => ({
        ...admin,
        isPlatformAdmin: true,
        role: 'platform_admin',
      })))
    } catch {
      toast('Failed to load platform admins', 'error')
    } finally {
      setLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    if (!search) return users
    const q = search.toLowerCase()
    return users.filter((u) => u.email?.toLowerCase().includes(q) || u.display_name?.toLowerCase().includes(q))
  }, [users, search])

  const stats = useMemo(() => ({
    total:   users.length,
    active:  users.filter(u => u.is_active !== false).length,
    inactive: users.filter(u => u.is_active === false).length,
  }), [users])

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Super-operator accounts</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6, maxWidth: 520 }}>
            Isolated from tenant-scoped users. Customer operators are managed inside each organization and workspace.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white"
          style={{ background: 'var(--gradient-primary)' }}
        >
          <Plus size={14} />
          Add Platform Admin
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Total Users"    value={loading ? '…' : stats.total}   color="var(--neon-indigo)"        icon={Users} />
        <StatCard label="Active"         value={loading ? '…' : stats.active}  color="var(--neon-green)"          icon={CheckCircle} />
        <StatCard label="Inactive"       value={loading ? '…' : stats.inactive} color="var(--color-accent-amber)" icon={Clock} />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px] flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <Search size={13} style={{ color: 'var(--text-muted)' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or email…"
            className="flex-1 bg-transparent outline-none"
            style={{ fontSize: 13, color: 'var(--text-primary)' }}
          />
          {search && <button onClick={() => setSearch('')}><X size={12} style={{ color: 'var(--text-muted)' }} /></button>}
        </div>
        <button onClick={load} className="p-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <RefreshCcw size={13} style={{ color: 'var(--text-muted)' }} />
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2, 3, 4, 5].map(i => <div key={i} className="glass rounded-xl h-14 skeleton" />)}</div>
      ) : (
        <div className="glass rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
          <table className="w-full" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['User', 'Role', 'Status', 'Scope', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>No platform admins found</td></tr>
              )}
              {filtered.map(u => {
                const rm = roleMeta(u.role)
                return (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }} className="hover:bg-elevated transition-colors">
                    <td style={{ padding: '10px 16px' }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{u.display_name || '—'}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.email}</div>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{ fontSize: 10, fontWeight: 700, background: rm.bg, color: rm.color, borderRadius: 999, padding: '3px 9px', textTransform: 'uppercase' }}>
                        {rm.label}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{
                        background: u.is_active !== false ? 'rgba(52,211,153,0.12)' : 'rgba(244,63,94,0.12)',
                        color: u.is_active !== false ? 'var(--neon-green)' : 'var(--color-accent-red)',
                        borderRadius: 999, padding: '3px 9px', fontSize: 11, fontWeight: 700,
                      }}>
                        {u.is_active !== false ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                        Global platform scope
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <button
                        onClick={() => setEditingAdmin(u)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                        style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                      >
                        <Edit size={12} />
                        Manage
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <PlatformAdminModal
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false)
            load()
          }}
          toast={toast}
        />
      )}

      {editingAdmin && (
        <PlatformAdminModal
          admin={editingAdmin}
          onClose={() => setEditingAdmin(null)}
          onSaved={() => {
            setEditingAdmin(null)
            load()
          }}
          toast={toast}
        />
      )}
    </div>
  )
}

function OverviewSection({ onNavigate }) {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [summary, setSummary] = useState(null)
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchBackendHealth().catch(() => null),
      fetchPlatformAnalytics().catch(() => null),
      fetchOrganizations().catch(() => []),
    ])
      .then(([healthResponse, summaryResponse, organizationsResponse]) => {
        setHealth(healthResponse)
        setSummary(summaryResponse)
        setOrgs(Array.isArray(organizationsResponse) ? organizationsResponse : [])
      })
      .finally(() => setLoading(false))
  }, [])

  const statusRows = [
    { label: 'Backend API', ok: health?.status === 'ok', detail: 'FastAPI + Uvicorn' },
    { label: 'Database', ok: true, detail: 'PostgreSQL' },
    { label: 'Redis / Queue', ok: true, detail: 'Redis + ARQ' },
    { label: 'AI Engine', ok: !(summary?.llm_circuit_breaker_open), detail: summary?.llm_circuit_breaker_open ? 'Circuit breaker open' : 'Inference available' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <SectionTitle>System Health</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {statusRows.map((row) => (
            <div key={row.label} className="pa-health-tile">
              {loading
                ? <div className="w-4 h-4 rounded-full animate-pulse" style={{ background: 'var(--border)' }} />
                : row.ok
                  ? <CheckCircle size={16} style={{ color: 'var(--neon-green)', flexShrink: 0 }} />
                  : <AlertTriangle size={16} style={{ color: 'var(--brand-orange)', flexShrink: 0 }} />}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{row.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{row.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Workspace Users" value={loading ? '…' : (summary?.total_users ?? '—')} color="var(--neon-indigo)" icon={Users} sub={`${summary?.active_users ?? 0} active`} />
        <StatCard label="Organizations" value={loading ? '…' : (summary?.total_organizations ?? orgs.length)} color="#22d3ee" icon={Globe} sub={`${summary?.active_organizations ?? 0} active`} />
        <StatCard label="Workspaces" value={loading ? '…' : (summary?.total_tenants ?? '—')} color="var(--brand-orange)" icon={Layers} sub={`${summary?.active_tenants ?? 0} active`} />
        <StatCard label="Active Incidents" value={loading ? '…' : (summary?.active_incidents ?? '—')} color="var(--brand-orange)" icon={AlertTriangle} sub={`${summary?.critical_incidents ?? 0} critical`} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Failed 24h" value={loading ? '…' : (summary?.failed_incidents_24h ?? '—')} color="var(--color-accent-red)" icon={XCircle} sub={`${((summary?.platform_error_rate_24h ?? 0) * 100).toFixed(1)}% error rate`} />
        <StatCard label="DLQ Entries" value={loading ? '…' : (summary?.dlq_entries ?? '—')} color="var(--color-accent-amber)" icon={AlertTriangle} sub="Queued worker failures" />
        <StatCard label="Circuit Breaker" value={loading ? '…' : (summary?.llm_circuit_breaker_open ? 'OPEN' : 'CLOSED')} color={summary?.llm_circuit_breaker_open ? 'var(--color-accent-red)' : 'var(--neon-green)'} icon={Brain} sub="LLM safety gate" />
        <StatCard label="Platform Admins" value={loading ? '…' : (summary?.total_platform_admins ?? '—')} color="var(--neon-cyan)" icon={ShieldCheck} sub={`${summary?.active_platform_admins ?? 0} active`} />
      </div>

      <div>
        <SectionTitle>Current Session</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { label: 'Logged in as', value: user?.email || '—', mono: false },
            { label: 'Role', value: (user?.role || '—').toUpperCase(), mono: true },
          ].map((item) => (
            <div key={item.label} className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</div>
              <div style={{ fontFamily: item.mono ? 'var(--font-mono)' : 'inherit', fontSize: 12, color: 'var(--text-heading)', marginTop: 4, wordBreak: 'break-all' }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionTitle>Quick Navigation</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {SECTIONS.filter((section) => section.id !== 'overview').map((section) => (
            <button
              key={section.id}
              onClick={() => onNavigate(section.id)}
              type="button"
              className="glass pa-quick-card rounded-xl p-4 flex items-center gap-3 text-left"
              style={{ border: '1px solid var(--border)', cursor: 'pointer' }}
            >
              <div className="p-2 rounded-lg" style={{ background: 'rgba(99,102,241,0.12)' }}>
                <section.icon size={15} style={{ color: 'var(--neon-indigo)' }} />
              </div>
              <div className="min-w-0">
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{section.label}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {section.id === 'organizations' && `${loading ? '…' : orgs.length} orgs`}
                  {section.id === 'workspaces' && 'Workspace management'}
                  {section.id === 'users' && 'Platform admin accounts'}
                  {section.id === 'integrations' && 'Global catalog definitions'}
                  {section.id === 'settings' && 'Runtime controls'}
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

function OrganizationsSection() {
  const { organizations: authOrganizations, tenants } = useAuth()
  const [remoteOrganizations, setRemoteOrganizations] = useState(null)
  const [organizationTenants, setOrganizationTenants] = useState({})
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(null)
  const [tenantListLoading, setTenantListLoading] = useState(false)

  const loadOrganizations = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    try {
      const data = await fetchOrganizations()
      setRemoteOrganizations(Array.isArray(data) ? data : null)
    } catch {
      setRemoteOrganizations(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadOrganizations()
  }, [loadOrganizations])

  const tenantCount = useCallback(
    (organization) => {
      if (organization.tenant_count != null) {
        return organization.tenant_count
      }
      return tenants?.filter((tenant) => String(tenant.organization_id) === String(organization.id)).length ?? 0
    },
    [tenants]
  )

  const organizations = useMemo(
    () => remoteOrganizations || authOrganizations || [],
    [remoteOrganizations, authOrganizations]
  )
  const totalTenantSpaces = useMemo(
    () => organizations.reduce((sum, organization) => sum + tenantCount(organization), 0),
    [organizations, tenantCount]
  )
  const selectedOrganization = organizations.find((organization) => String(organization.id) === String(selectedOrganizationId)) || organizations[0] || null
  const selectedOrganizationTenantList = organizationTenants[String(selectedOrganization?.id)] || null
  const selectedOrganizationTenants = useMemo(
    () => selectedOrganizationTenantList || (tenants || []).filter((tenant) => String(tenant.organization_id) === String(selectedOrganization?.id)),
    [selectedOrganization?.id, selectedOrganizationTenantList, tenants]
  )

  useEffect(() => {
    if (!organizations.length) {
      setSelectedOrganizationId(null)
      return
    }
    setSelectedOrganizationId((current) => (
      organizations.some((organization) => String(organization.id) === String(current))
        ? current
        : organizations[0].id
    ))
  }, [organizations])

  useEffect(() => {
    if (!selectedOrganization?.id) {
      return
    }
    const organizationId = String(selectedOrganization.id)
    if (organizationTenants[organizationId]) {
      return
    }

    let cancelled = false
    setTenantListLoading(true)
    fetchOrganizationTenants(selectedOrganization.id)
      .then((data) => {
        if (cancelled) return
        setOrganizationTenants((current) => ({
          ...current,
          [organizationId]: Array.isArray(data) ? data : [],
        }))
      })
      .catch(() => {
        if (cancelled) return
        setOrganizationTenants((current) => ({
          ...current,
          [organizationId]: [],
        }))
      })
      .finally(() => {
        if (!cancelled) {
          setTenantListLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [organizationTenants, selectedOrganization?.id, selectedOrganization])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Customer directory</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6, maxWidth: 480 }}>
            Select an organization to inspect workspaces, or create a new customer record.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadOrganizations(true)}
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

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Organizations" value={loading ? '…' : organizations.length} color="#22d3ee" icon={Globe} />
        <StatCard label="Workspaces" value={loading ? '…' : totalTenantSpaces} color="var(--brand-orange)" icon={Layers} />
      </div>

      <div>
        <SectionTitle>All Organizations</SectionTitle>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((item) => (
              <div key={item} className="glass rounded-xl animate-pulse" style={{ border: '1px solid var(--border)', height: 76 }} />
            ))}
          </div>
        ) : organizations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 rounded-xl" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            <Building2 size={28} style={{ opacity: 0.3, marginBottom: 10 }} />
            <p style={{ fontSize: 13 }}>No organizations found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-6">
            <div className="space-y-2">
            {organizations.map((organization) => {
              const totalTenants = tenantCount(organization)
              const isSelected = String(selectedOrganizationId) === String(organization.id)
              return (
                <button
                  key={organization.id}
                  type="button"
                  onClick={() => setSelectedOrganizationId(organization.id)}
                  className="glass rounded-xl p-4 flex items-center justify-between gap-4 w-full text-left transition-all"
                  style={{
                    border: isSelected ? '1px solid rgba(34,211,238,0.35)' : '1px solid var(--border)',
                    boxShadow: isSelected ? '0 0 0 1px rgba(34,211,238,0.08)' : 'none',
                  }}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                      <Building2 size={16} style={{ color: 'var(--text-muted)' }} />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{organization.name}</span>
                        {organization.status && <StatusBadge status={organization.status} />}
                      </div>
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 1 }}>{organization.slug}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="hidden sm:flex items-center gap-1.5" style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      <Layers size={12} />
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{totalTenants}</span>
                      <span>workspace{totalTenants !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', fontSize: 12, color: isSelected ? '#22d3ee' : 'var(--text-muted)' }}>
                      <Settings size={12} />
                      {isSelected ? 'Viewing workspaces' : 'View workspaces'}
                    </div>
                  </div>
                </button>
              )
            })}
            </div>

            <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
              <SectionTitle>{selectedOrganization ? `${selectedOrganization.name} Workspaces` : 'Organization Workspaces'}</SectionTitle>
              {!selectedOrganization ? (
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Select an organization to view its workspaces.</div>
              ) : tenantListLoading && !selectedOrganizationTenantList ? (
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading workspaces…</div>
              ) : selectedOrganizationTenants.length === 0 ? (
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No workspaces are assigned to this organization yet.</div>
              ) : (
                <div className="space-y-3">
                  {selectedOrganizationTenants.map((tenant) => (
                    <div key={tenant.id} className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{tenant.display_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>{tenant.name}</div>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <StatusBadge status={tenant.is_active === false ? 'disabled' : 'active'} />
                          <span style={{ fontSize: 10, padding: '3px 8px', borderRadius: 999, border: '1px solid var(--border)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                            {tenant.cloud || 'unknown'}
                          </span>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Credential Status</div>
                          <div style={{ fontSize: 12, color: 'var(--text-heading)', marginTop: 4 }}>{tenant.credential_status || 'Not configured'}</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Escalation Email</div>
                          <div style={{ fontSize: 12, color: 'var(--text-heading)', marginTop: 4 }}>{tenant.escalation_email || 'Not configured'}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateOrgModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false)
            loadOrganizations(true)
          }}
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

  const autoSlug = useCallback(
    (value) => value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
    []
  )

  const handleSave = async () => {
    if (!name.trim() || !slug.trim()) {
      toast('Name and slug are required', 'error')
      return
    }
    setSaving(true)
    try {
      await createOrganization({ name: name.trim(), slug: slug.trim() })
      toast('Organization created')
      onCreated()
    } catch (error) {
      toast(extractErrorMessage(error) || 'Create failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div className="relative w-full max-w-md mx-4 glass rounded-2xl p-6 space-y-4" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>Create Organization</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Organization Name</label>
          <input value={name} onChange={(event) => { setName(event.target.value); setSlug(autoSlug(event.target.value)) }} placeholder="Acme Corp" style={inputCls} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug (URL-safe)</label>
          <input value={slug} onChange={(event) => setSlug(autoSlug(event.target.value))} placeholder="acme-corp" style={{ ...inputCls, fontFamily: 'var(--font-mono)', fontSize: 12 }} />
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

function IntegrationCatalogSection() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({
    key: '',
    display_name: '',
    category: 'monitoring',
    enabled: true,
    supports_webhook: true,
    supports_polling: false,
    supports_sync: true,
    config_schema_json: '{\n  "type": "object",\n  "properties": {},\n  "required": []\n}',
  })

  const loadItems = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    try {
      const response = await fetchIntegrationTypes({ includeDisabled: true })
      setItems(Array.isArray(response) ? response : [])
    } catch (error) {
      setItems([])
      toast(extractErrorMessage(error) || 'Failed to load integration catalog', 'error')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [toast])

  useEffect(() => {
    loadItems()
  }, [loadItems])

  const enabledCount = useMemo(() => items.filter((item) => item.enabled).length, [items])

  const resetForm = useCallback(() => {
    setEditingId(null)
    setForm({
      key: '',
      display_name: '',
      category: 'monitoring',
      enabled: true,
      supports_webhook: true,
      supports_polling: false,
      supports_sync: true,
      config_schema_json: '{\n  "type": "object",\n  "properties": {},\n  "required": []\n}',
    })
  }, [])

  const parseSchema = () => {
    try {
      const parsed = JSON.parse(form.config_schema_json || '{}')
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('Schema must be a JSON object')
      }
      return parsed
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : 'Invalid schema JSON')
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    let schema
    try {
      schema = parseSchema()
    } catch (error) {
      toast(error.message, 'error')
      return
    }

    const payload = {
      key: form.key.trim().toLowerCase(),
      display_name: form.display_name.trim(),
      category: form.category.trim().toLowerCase(),
      enabled: form.enabled,
      supports_webhook: form.supports_webhook,
      supports_polling: form.supports_polling,
      supports_sync: form.supports_sync,
      config_schema_json: schema,
    }

    if (!payload.key || !payload.display_name || !payload.category) {
      toast('Key, display name, and category are required', 'error')
      return
    }

    setSaving(true)
    try {
      if (editingId) {
        await updateIntegrationType(editingId, payload)
        toast('Integration type updated')
      } else {
        await createIntegrationType(payload)
        toast('Integration type created')
      }
      resetForm()
      await loadItems(true)
    } catch (error) {
      toast(extractErrorMessage(error) || 'Failed to save integration type', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (item) => {
    setEditingId(item.id)
    setForm({
      key: item.key || '',
      display_name: item.display_name || '',
      category: item.category || 'monitoring',
      enabled: Boolean(item.enabled),
      supports_webhook: Boolean(item.supports_webhook),
      supports_polling: Boolean(item.supports_polling),
      supports_sync: Boolean(item.supports_sync),
      config_schema_json: JSON.stringify(item.config_schema_json || {}, null, 2),
    })
  }

  const handleDisable = async (item) => {
    if (!window.confirm(`Disable ${item.display_name}? Existing tenant integrations will remain, but the catalog entry will stop being offered for new setup.`)) {
      return
    }
    try {
      await deleteIntegrationType(item.id)
      toast('Integration type disabled')
      if (editingId === item.id) {
        resetForm()
      }
      await loadItems(true)
    } catch (error) {
      toast(extractErrorMessage(error) || 'Failed to disable integration type', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Global definitions</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6, maxWidth: 480 }}>
            Schema-backed types that workspaces instantiate — webhooks, polling, and sync capabilities.
          </p>
        </div>
        <button
          onClick={() => loadItems(true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
        >
          <RefreshCcw size={11} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Catalog Entries" value={loading ? '…' : items.length} color="var(--neon-indigo)" icon={Zap} />
        <StatCard label="Enabled" value={loading ? '…' : enabledCount} color="var(--neon-green)" icon={CheckCircle} />
        <StatCard label="Webhook Ready" value={loading ? '…' : items.filter((item) => item.supports_webhook).length} color="var(--neon-cyan)" icon={Globe} />
        <StatCard label="Sync Ready" value={loading ? '…' : items.filter((item) => item.supports_sync).length} color="var(--brand-orange)" icon={Layers} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
        <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)' }}>
          <SectionTitle>Catalog Entries</SectionTitle>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((item) => (
                <div key={item} className="rounded-lg animate-pulse" style={{ height: 74, background: 'var(--bg-input)', border: '1px solid var(--border)' }} />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center" style={{ color: 'var(--text-muted)' }}>
              No integration types defined.
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <div key={item.id} className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{item.display_name}</span>
                        <StatusBadge status={item.enabled ? 'active' : 'disabled'} />
                        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{item.category}</span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>{item.key}</div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button onClick={() => handleEdit(item)} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--glow-indigo)', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--neon-indigo)' }}>
                        Edit
                      </button>
                      <button onClick={() => handleDisable(item)} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'rgba(244,63,94,0.10)', border: '1px solid rgba(244,63,94,0.22)', color: 'var(--color-accent-red)' }}>
                        Disable
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap mt-3">
                    {[
                      ['Webhook', item.supports_webhook],
                      ['Polling', item.supports_polling],
                      ['Sync', item.supports_sync],
                    ].map(([label, enabled]) => (
                      <span key={label} style={{ fontSize: 10, padding: '3px 8px', borderRadius: 999, border: '1px solid var(--border)', color: enabled ? 'var(--neon-cyan)' : 'var(--text-muted)', background: enabled ? 'rgba(34,211,238,0.08)' : 'transparent' }}>
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <SectionTitle>{editingId ? 'Edit Entry' : 'New Entry'}</SectionTitle>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {editingId ? 'Update the catalog definition and schema used for new tenant integrations.' : 'Add a new integration type to the global catalog.'}
              </p>
            </div>
            {editingId && (
              <button type="button" onClick={resetForm} className="px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                Cancel edit
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Key</div>
              <input value={form.key} onChange={(event) => setForm((current) => ({ ...current, key: event.target.value }))} placeholder="site24x7" style={{ ...inputCls, fontFamily: 'var(--font-mono)', fontSize: 12 }} />
            </label>
            <label>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Display Name</div>
              <input value={form.display_name} onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))} placeholder="Site24x7" style={inputCls} />
            </label>
          </div>

          <label>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Category</div>
            <input value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))} placeholder="monitoring" style={{ ...inputCls, fontFamily: 'var(--font-mono)', fontSize: 12 }} />
          </label>

          <div className="grid grid-cols-2 gap-3">
            {[
              ['enabled', 'Enabled'],
              ['supports_webhook', 'Webhook'],
              ['supports_polling', 'Polling'],
              ['supports_sync', 'Sync'],
            ].map(([field, label]) => (
              <label key={field} className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-secondary)' }}>
                <input type="checkbox" checked={Boolean(form[field])} onChange={(event) => setForm((current) => ({ ...current, [field]: event.target.checked }))} />
                {label}
              </label>
            ))}
          </div>

          <label>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Config Schema JSON</div>
            <textarea value={form.config_schema_json} onChange={(event) => setForm((current) => ({ ...current, config_schema_json: event.target.value }))} style={textareaCls} spellCheck={false} />
          </label>

          <button type="submit" disabled={saving} className="w-full py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Saving…' : editingId ? 'Update Integration Type' : 'Create Integration Type'}
          </button>
        </form>
      </div>
    </div>
  )
}

function SettingsSection() {
  const toast = useToast()
  const [settings, setSettingsState] = useState(null)
  const [form, setForm] = useState(null)
  const [dlq, setDlq] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dlqLoading, setDlqLoading] = useState(false)
  const [replayingIndex, setReplayingIndex] = useState(null)
  const [clearing, setClearing] = useState(false)

  const syncForm = useCallback((source) => {
    if (!source) {
      setForm(null)
      return
    }
    setForm({
      llm_provider: source.llm_provider ?? '',
      llm_primary_model: source.llm_primary_model ?? '',
      llm_fallback_model: source.llm_fallback_model ?? '',
      llm_circuit_breaker_threshold: String(source.llm_circuit_breaker_threshold ?? ''),
      llm_circuit_breaker_cooldown: String(source.llm_circuit_breaker_cooldown ?? ''),
      investigation_timeout: String(source.investigation_timeout ?? ''),
      execution_timeout: String(source.execution_timeout ?? ''),
      verification_timeout: String(source.verification_timeout ?? ''),
      max_investigation_retries: String(source.max_investigation_retries ?? ''),
      max_execution_retries: String(source.max_execution_retries ?? ''),
      max_verification_retries: String(source.max_verification_retries ?? ''),
      lock_ttl: String(source.lock_ttl ?? ''),
    })
  }, [])

  const loadData = useCallback(async () => {
    const [settingsResponse, dlqResponse] = await Promise.all([
      fetchSettings().catch(() => null),
      fetchDLQ({ limit: 50 }).catch(() => ({ items: [] })),
    ])
    setSettingsState(settingsResponse)
    syncForm(settingsResponse)
    setDlq(dlqResponse?.items || [])
  }, [syncForm])

  useEffect(() => {
    loadData().finally(() => setLoading(false))
  }, [loadData])

  const reloadDlq = async () => {
    setDlqLoading(true)
    try {
      const response = await fetchDLQ({ limit: 50 })
      setDlq(response?.items || [])
    } finally {
      setDlqLoading(false)
    }
  }

  const handleFormChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const handleSave = async () => {
    if (!form) {
      return
    }

    const numberFields = [
      'llm_circuit_breaker_threshold',
      'llm_circuit_breaker_cooldown',
      'investigation_timeout',
      'execution_timeout',
      'verification_timeout',
      'max_investigation_retries',
      'max_execution_retries',
      'max_verification_retries',
      'lock_ttl',
    ]

    const payload = {
      llm_provider: form.llm_provider.trim(),
      llm_primary_model: form.llm_primary_model.trim(),
      llm_fallback_model: form.llm_fallback_model.trim(),
    }

    for (const field of numberFields) {
      const value = Number(form[field])
      if (!Number.isFinite(value)) {
        toast(`Invalid value for ${field.replaceAll('_', ' ')}`, 'error')
        return
      }
      payload[field] = value
    }

    setSaving(true)
    try {
      await updateSettings(payload)
      const nextSettings = {
        ...settings,
        ...payload,
      }
      setSettingsState(nextSettings)
      syncForm(nextSettings)
      toast('Platform settings updated')
    } catch (error) {
      toast(extractErrorMessage(error) || 'Failed to update settings', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleReplay = async (index) => {
    setReplayingIndex(index)
    try {
      await replayDLQEntry(index)
      toast('DLQ entry replayed')
      await reloadDlq()
    } catch (error) {
      toast(extractErrorMessage(error) || 'Replay failed', 'error')
    } finally {
      setReplayingIndex(null)
    }
  }

  const handleClearDlq = async () => {
    if (!window.confirm('Clear all DLQ entries? This cannot be undone.')) {
      return
    }
    setClearing(true)
    try {
      await clearDLQ()
      setDlq([])
      toast('DLQ cleared')
    } catch (error) {
      toast(extractErrorMessage(error) || 'Clear failed', 'error')
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Runtime configuration</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6, maxWidth: 520 }}>
          AI routing, pipeline limits, and safety thresholds for the running API — applied in-memory until persisted.
        </p>
      </div>

      {loading || !form ? (
        <div className="space-y-3">
          {[1, 2, 3].map((item) => <div key={item} className="glass rounded-xl h-20 skeleton" style={{ border: '1px solid var(--border)' }} />)}
        </div>
      ) : (
        <>
          <div className="glass rounded-xl p-5 space-y-5" style={{ border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <SectionTitle>Runtime Controls</SectionTitle>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>These values are applied in-memory for the running API process so platform admins can tune behavior without editing env vars first.</p>
              </div>
              <button onClick={handleSave} disabled={saving} className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
                {saving ? 'Saving…' : 'Save Settings'}
              </button>
            </div>

            <div>
              <SectionTitle>AI Engine</SectionTitle>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Provider</div>
                  <input value={form.llm_provider} onChange={(event) => handleFormChange('llm_provider', event.target.value)} style={inputCls} />
                </label>
                <label>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Primary Model</div>
                  <input value={form.llm_primary_model} onChange={(event) => handleFormChange('llm_primary_model', event.target.value)} style={{ ...inputCls, fontFamily: 'var(--font-mono)', fontSize: 12 }} />
                </label>
                <label>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Fallback Model</div>
                  <input value={form.llm_fallback_model} onChange={(event) => handleFormChange('llm_fallback_model', event.target.value)} style={{ ...inputCls, fontFamily: 'var(--font-mono)', fontSize: 12 }} />
                </label>
                <label>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Circuit Breaker Threshold</div>
                  <input value={form.llm_circuit_breaker_threshold} onChange={(event) => handleFormChange('llm_circuit_breaker_threshold', event.target.value)} style={inputCls} inputMode="numeric" />
                </label>
                <label>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Circuit Breaker Cooldown (s)</div>
                  <input value={form.llm_circuit_breaker_cooldown} onChange={(event) => handleFormChange('llm_circuit_breaker_cooldown', event.target.value)} style={inputCls} inputMode="numeric" />
                </label>
              </div>
            </div>

            <div>
              <SectionTitle>Pipeline Limits</SectionTitle>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[
                  ['investigation_timeout', 'Investigation Timeout (s)'],
                  ['execution_timeout', 'Execution Timeout (s)'],
                  ['verification_timeout', 'Verification Timeout (s)'],
                  ['max_investigation_retries', 'Max Investigation Retries'],
                  ['max_execution_retries', 'Max Execution Retries'],
                  ['max_verification_retries', 'Max Verification Retries'],
                  ['lock_ttl', 'Redis Lock TTL (s)'],
                ].map(([field, label]) => (
                  <label key={field}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
                    <input value={form[field]} onChange={(event) => handleFormChange(field, event.target.value)} style={inputCls} inputMode="numeric" />
                  </label>
                ))}
              </div>
            </div>
          </div>

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
                    <button onClick={handleClearDlq} disabled={clearing} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold" style={{ background: 'rgba(244,63,94,0.10)', border: '1px solid rgba(244,63,94,0.25)', color: 'var(--color-accent-red)' }}>
                      <Trash2 size={11} />
                      {clearing ? 'Clearing…' : 'Clear All'}
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
                  {dlq.map((entry, index) => (
                    <div key={index} className="flex items-center justify-between gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                      <div className="min-w-0">
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>
                          {entry.function || entry.job_id || `Entry #${index}`}
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
                      <button onClick={() => handleReplay(index)} disabled={replayingIndex === index} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold flex-shrink-0" style={{ background: 'var(--glow-indigo)', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--neon-indigo)' }}>
                        {replayingIndex === index ? <RefreshCcw size={11} className="animate-spin" /> : <ArrowRightCircle size={11} />}
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

export default function PlatformAdminPage() {
  const { user, logout } = useAuth()
  const { isDark, toggle: toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const activeSection = searchParams.get('section') || 'overview'
  const setSection = useCallback((id) => {
    setSearchParams({ section: id }, { replace: true })
  }, [setSearchParams])

  const displayRole = (user?.role || '').replace(/_/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase())

  return (
    <div className="platform-admin min-h-screen" style={{ background: 'var(--bg-body)', color: 'var(--text-primary)' }}>
      {/* ── Top Bar ── */}
      <header className="pa-topbar flex items-center justify-between px-6 py-3 sticky top-0 z-40">
        <div className="flex items-center gap-4">
          <div className="pa-brand-mark">
            <Globe size={18} style={{ color: '#22d3ee' }} aria-hidden />
          </div>
          <div className="pa-title-stack">
            <span className="pa-kicker">AIREX</span>
            <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>Platform Admin</span>
          </div>
          {user?.role && (
            <span className="px-2 py-0.5 rounded-full" style={{ fontSize: 10, fontWeight: 700, background: 'rgba(34,211,238,0.10)', color: '#22d3ee', border: '1px solid rgba(34,211,238,0.22)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {displayRole}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div className="pa-chip-scope">
            <ShieldCheck size={12} style={{ color: 'var(--neon-green)', flexShrink: 0 }} aria-hidden />
            Platform scope
          </div>
          {user?.displayName && (
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{user.displayName}</span>
          )}
          {/* ── Theme Toggle ── */}
          <button
            onClick={toggleTheme}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2 rounded-lg transition-all hover:opacity-80"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          {logout && (
            <button
              onClick={() => { logout(); navigate('/admin/login') }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-opacity hover:opacity-70"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
            >
              <LogOut size={12} />
              Sign out
            </button>
          )}
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-57px)]">
        {/* ── Sidebar ── */}
        <nav className="pa-sidebar" aria-label="Platform admin sections">
          <p className="pa-nav-label">Navigate</p>
          {SECTIONS.map((section) => {
            const isActive = activeSection === section.id
            return (
              <button
                key={section.id}
                type="button"
                onClick={() => setSection(section.id)}
                className={`pa-nav-btn ${isActive ? 'pa-nav-btn--active' : ''}`}
              >
                <span className="pa-nav-icon-wrap">
                  <section.icon size={15} strokeWidth={2} />
                </span>
                {section.label}
              </button>
            )
          })}
        </nav>

        {/* ── Main Content ── */}
        <main className="flex-1 overflow-auto">
          <div className="pa-main-inner">
            <PageHero sectionId={activeSection} />
            {activeSection === 'overview' && <OverviewSection onNavigate={setSection} />}
            {activeSection === 'organizations' && <OrganizationsSection />}
            {activeSection === 'workspaces' && (
              <div className="space-y-6">
                <TenantWorkspaceManager mode="platform" />
              </div>
            )}
            {activeSection === 'users' && <UsersSection />}
            {activeSection === 'integrations' && <IntegrationCatalogSection />}
            {activeSection === 'settings' && <SettingsSection />}
          </div>
        </main>
      </div>
    </div>
  )
}
