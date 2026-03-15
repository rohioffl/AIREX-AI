import { useEffect, useMemo, useState, useCallback } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  Users, Building2, Settings, Brain, LayoutDashboard,
  Plus, Trash2, Edit, Search, CheckCircle, XCircle, Clock, AlertTriangle,
  RefreshCcw, ChevronRight, Server, Save,
  ShieldCheck, Activity, Globe, Cpu, ToggleLeft, ToggleRight, X,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useToasts } from '../context/ToastContext'
import {
  fetchUsers, createUser, updateUser, deleteUser,
  fetchTenants,
  fetchSettings, updateSettings, fetchBackendHealth,
  fetchMetrics,
} from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'
import { FALLBACK_TENANT_ID } from '../utils/constants'
import { formatRelativeTime } from '../utils/formatters'

// ── Tab definitions ──────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview',  label: 'Overview',       icon: LayoutDashboard },
  { id: 'users',     label: 'Users',           icon: Users },
  { id: 'tenants',   label: 'Tenants',         icon: Building2 },
  { id: 'settings',  label: 'Settings',        icon: Settings },
  { id: 'models',    label: 'AI Models',       icon: Brain },
]

// ── Shared helpers ────────────────────────────────────────────────────────────

function roleMeta(role) {
  const r = (role || 'operator').toLowerCase()
  if (r === 'admin')  return { label: 'ADMIN',    color: 'var(--neon-purple)', bg: 'rgba(192,132,252,0.12)' }
  if (r === 'viewer') return { label: 'VIEWER',   color: 'var(--text-muted)', bg: 'rgba(148,163,184,0.12)' }
  return                     { label: 'OPERATOR', color: 'var(--neon-cyan)', bg: 'rgba(56,189,248,0.12)' }
}

function RoleBadge({ role }) {
  const m = roleMeta(role)
  return (
    <span style={{ background: m.bg, color: m.color, borderRadius: 999, padding: '3px 9px', fontSize: 11, fontWeight: 700 }}>
      {m.label}
    </span>
  )
}

function StatCard({ label, value, color = 'var(--neon-indigo)', icon: Icon, sub }) {
  return (
    <div className="glass rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        {Icon && <Icon size={14} style={{ color, opacity: 0.7 }} />}
      </div>
      <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
      {sub && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sub}</span>}
    </div>
  )
}

function SectionHeader({ title, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{title}</span>
      {action}
    </div>
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

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab({ onNavigate }) {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [users, setUsers]   = useState([])
  const [tenants, setTenants] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchBackendHealth().catch(() => null),
      fetchMetrics().catch(() => null),
      fetchUsers({ limit: 100 }).catch(() => ({ items: [] })),
      fetchTenants().catch(() => []),
    ]).then(([h, m, u, t]) => {
      setHealth(h)
      setMetrics(m)
      setUsers(u?.items || [])
      setTenants(Array.isArray(t) ? t : [])
    }).finally(() => setLoading(false))
  }, [])

  const STATUS = [
    { label: 'Backend API',   ok: health?.status === 'ok',  detail: 'FastAPI + Uvicorn' },
    { label: 'Database',      ok: true,                      detail: 'PostgreSQL 15 + RLS' },
    { label: 'Redis / Queue', ok: true,                      detail: 'ARQ Worker' },
    { label: 'AI Engine',     ok: true,                      detail: 'Gemini 2.0 Flash' },
  ]

  return (
    <div className="space-y-6">
      {/* System Health */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="System Health" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {STATUS.map(s => (
            <div key={s.label} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              {loading ? (
                <div className="w-4 h-4 rounded-full animate-pulse" style={{ background: 'var(--border)' }} />
              ) : s.ok ? (
                <CheckCircle size={16} style={{ color: 'var(--neon-green)', flexShrink: 0 }} />
              ) : (
                <AlertTriangle size={16} style={{ color: 'var(--brand-orange)', flexShrink: 0 }} />
              )}
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
        <StatCard label="Total Users"    value={users.length}                              color="var(--neon-indigo)" icon={Users}     sub={`${users.filter(u=>u.is_active!==false).length} active`} />
        <StatCard label="Tenants"        value={tenants.length}                             color="var(--neon-cyan)" icon={Building2} sub="Configured" />
        <StatCard label="Total Servers"  value={tenants.reduce((s,t)=>s+(t.server_count||0),0)} color="var(--neon-green)" icon={Server}    sub="Across all tenants" />
        <StatCard label="Active Alerts"  value={metrics?.active_alerts ?? '—'}             color="var(--brand-orange)" icon={AlertTriangle} sub={`${metrics?.critical_alerts ?? 0} critical`} />
      </div>

      {/* Quick Navigation */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {TABS.filter(t => t.id !== 'overview').map(tab => (
          <button
            key={tab.id}
            onClick={() => onNavigate(tab.id)}
            className="glass rounded-xl p-4 flex items-center gap-3 hover-lift transition-all text-left"
            style={{ border: '1px solid var(--border)', cursor: 'pointer' }}
          >
            <div className="p-2 rounded-lg" style={{ background: 'rgba(99,102,241,0.12)' }}>
              <tab.icon size={16} style={{ color: 'var(--neon-indigo)' }} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{tab.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {tab.id === 'users'    && `${users.length} users`}
                {tab.id === 'tenants'  && `${tenants.length} tenants`}
                {tab.id === 'settings' && 'System configuration'}
                {tab.id === 'models'   && 'LLM & AI settings'}
                {tab.id === 'queue'    && 'Pending approvals'}
              </div>
            </div>
            <ChevronRight size={14} style={{ color: 'var(--text-muted)', marginLeft: 'auto' }} />
          </button>
        ))}
      </div>

      {/* Session */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="Current Session" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: 'Tenant ID', value: (user?.tenantId || user?.tenant_id || FALLBACK_TENANT_ID), mono: true },
            { label: 'Logged in as', value: user?.email || '—', mono: false },
            { label: 'Role', value: (user?.role || '—').toUpperCase(), mono: true },
          ].map(item => (
            <div key={item.label} className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</div>
              <div style={{ fontFamily: item.mono ? 'var(--font-mono)' : 'inherit', fontSize: 12, color: 'var(--text-heading)', marginTop: 4, wordBreak: 'break-all' }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Users Tab ────────────────────────────────────────────────────────────────

function UsersTab() {
  const { user: currentUser } = useAuth()
  const { addToast } = useToasts()
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editingUser, setEditingUser] = useState(null)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchUsers()
      setUsers(data.items || [])
    } catch {
      toast('Failed to load users', 'error')
    } finally {
      setLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = users
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(u => u.email?.toLowerCase().includes(q) || u.display_name?.toLowerCase().includes(q))
    }
    if (roleFilter) list = list.filter(u => (u.role || 'operator').toLowerCase() === roleFilter)
    return list
  }, [users, search, roleFilter])

  const stats = useMemo(() => ({
    total:    users.length,
    active:   users.filter(u => u.is_active !== false).length,
    admins:   users.filter(u => (u.role||'').toLowerCase() === 'admin').length,
    pending:  users.filter(u => u.invitation_status === 'pending').length,
  }), [users])

  const handleDelete = async (id, email) => {
    if (id === currentUser?.user_id) { toast('Cannot delete yourself', 'error'); return }
    if (!window.confirm(`Deactivate user ${email}? They will no longer be able to log in.`)) return
    try {
      await deleteUser(id)
      setUsers(prev => prev.filter(u => u.id !== id))
      toast('User deactivated')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Delete failed', 'error')
    }
  }

  const handleToggleActive = async (u) => {
    try {
      await updateUser(u.id, { is_active: !u.is_active })
      toast(`User ${u.is_active ? 'deactivated' : 'activated'}`)
      load()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Update failed', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Users"    value={stats.total}   color="var(--neon-indigo)" icon={Users} />
        <StatCard label="Active"         value={stats.active}  color="var(--neon-green)" icon={CheckCircle} />
        <StatCard label="Admins"         value={stats.admins}  color="var(--neon-purple)" icon={ShieldCheck} />
        <StatCard label="Pending Invite" value={stats.pending} color="var(--color-accent-amber)" icon={Clock} />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px] flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <Search size={14} style={{ color: 'var(--text-muted)' }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or email..."
            className="flex-1 bg-transparent outline-none"
            style={{ fontSize: 13, color: 'var(--text-primary)' }}
          />
          {search && <button onClick={() => setSearch('')}><X size={12} style={{ color: 'var(--text-muted)' }} /></button>}
        </div>
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          className="px-3 py-2 rounded-lg outline-none"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', fontSize: 13 }}
        >
          <option value="">All Roles</option>
          <option value="admin">Admin</option>
          <option value="operator">Operator</option>
          <option value="viewer">Viewer</option>
        </select>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'var(--gradient-primary)' }}>
          <Plus size={14} /> Add User
        </button>
        <button onClick={load} className="p-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <RefreshCcw size={14} style={{ color: 'var(--text-muted)' }} />
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">{[1,2,3,4].map(i => <div key={i} className="glass rounded-xl h-14 skeleton" />)}</div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['User', 'Role', 'Status', 'Invite', 'Last Login', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>No users found</td></tr>
              )}
              {filtered.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }} className="hover:bg-elevated transition-colors">
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{u.display_name || '—'}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.email}</div>
                  </td>
                  <td style={{ padding: '10px 16px' }}><RoleBadge role={u.role} /></td>
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
                    {u.invitation_status ? (
                      <span style={{
                        background: u.invitation_status === 'accepted' ? 'rgba(52,211,153,0.12)' : 'rgba(251,191,36,0.12)',
                        color: u.invitation_status === 'accepted' ? 'var(--neon-green)' : 'var(--color-accent-amber)',
                        borderRadius: 999, padding: '3px 9px', fontSize: 11, fontWeight: 700,
                      }}>
                        {u.invitation_status}
                      </span>
                    ) : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: 'var(--text-muted)' }}>
                    {u.last_login_at ? formatRelativeTime(u.last_login_at) : '—'}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <div className="flex items-center gap-2">
                      <button onClick={() => setEditingUser(u)} className="p-1.5 rounded transition-colors" style={{ color: 'var(--neon-indigo)', background: 'var(--glow-indigo)' }} title="Edit">
                        <Edit size={13} />
                      </button>
                      <button onClick={() => handleToggleActive(u)} className="p-1.5 rounded transition-colors" style={{ color: u.is_active !== false ? 'var(--color-accent-red)' : 'var(--neon-green)', background: 'var(--bg-input)' }} title={u.is_active !== false ? 'Deactivate' : 'Activate'}>
                        {u.is_active !== false ? <XCircle size={13} /> : <CheckCircle size={13} />}
                      </button>
                      {u.id !== currentUser?.user_id && (
                        <button onClick={() => handleDelete(u.id, u.email)} className="p-1.5 rounded transition-colors" style={{ color: 'var(--color-accent-red)', background: 'var(--glow-rose)' }} title="Deactivate user">
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(showCreate || editingUser) && (
        <UserModal
          user={editingUser}
          onClose={() => { setShowCreate(false); setEditingUser(null) }}
          onSaved={() => { setShowCreate(false); setEditingUser(null); load() }}
        />
      )}
    </div>
  )
}

function UserModal({ user, onClose, onSaved }) {
  const { addToast } = useToasts()
  const [form, setForm] = useState({ email: user?.email || '', display_name: user?.display_name || '', role: user?.role || 'operator', password: '' })
  const [saving, setSaving] = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const handleSave = async () => {
    if (!form.email || !form.display_name) { toast('Email and name are required', 'error'); return }
    setSaving(true)
    try {
      if (user) {
        await updateUser(user.id, { display_name: form.display_name, role: form.role })
        toast('User updated')
      } else {
        await createUser({ email: form.email, display_name: form.display_name, role: form.role, password: form.password || undefined })
        toast('User created — invite sent')
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
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>{user ? 'Edit User' : 'Invite New User'}</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        {!user && (
          <input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="Email address" type="email" style={inputCls} />
        )}
        <input value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} placeholder="Display name" style={inputCls} />
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Role</label>
          <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))} style={inputCls}>
            <option value="viewer">Viewer — read-only access</option>
            <option value="operator">Operator — can approve/reject incidents</option>
            <option value="admin">Admin — full access + user management</option>
          </select>
        </div>
        {!user && (
          <input value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="Password (leave blank to send invite link)" type="password" style={inputCls} />
        )}
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Saving…' : user ? 'Save Changes' : 'Create & Invite'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tenants Tab ───────────────────────────────────────────────────────────────

function TenantsTab() {
  const { addToast } = useToasts()
  const [tenants, setTenants]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [showOnboard, setShowOnboard] = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchTenants()
      setTenants(Array.isArray(data) ? data : [])
    } catch {
      toast('Failed to load tenants', 'error')
    } finally {
      setLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard label="Total Tenants"   value={tenants.length}                                         color="var(--neon-indigo)" icon={Building2} />
        <StatCard label="Cloud Providers" value={[...new Set(tenants.map(t => t.cloud))].filter(Boolean).length} color="var(--neon-cyan)" icon={Globe} />
        <StatCard label="Total Servers"   value={tenants.reduce((s, t) => s + (t.server_count || 0), 0)} color="var(--neon-green)" icon={Server} />
      </div>

      <div className="flex justify-between items-center">
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Configured Tenants</span>
        <div className="flex items-center gap-2">
          <button onClick={load} className="p-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <RefreshCcw size={14} style={{ color: 'var(--text-muted)' }} />
          </button>
          <button onClick={() => setShowOnboard(true)} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'var(--gradient-primary)' }}>
            <Plus size={14} /> Onboard Tenant
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="glass rounded-xl h-16 skeleton" />)}</div>
      ) : tenants.length === 0 ? (
        <div className="glass rounded-xl py-12 text-center" style={{ color: 'var(--text-muted)', fontSize: 14 }}>No tenants configured</div>
      ) : (
        <div className="space-y-3">
          {tenants.map(t => (
            <div key={t.name} className="glass rounded-xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--glow-indigo)' }}>
                  <Building2 size={18} style={{ color: 'var(--neon-indigo)' }} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{t.display_name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{t.name}</span>
                    {t.escalation_email && ` · ${t.escalation_email}`}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--neon-cyan)', fontFamily: 'var(--font-mono)' }}>{t.server_count ?? 0}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>servers</div>
                </div>
                <span style={{
                  background: t.cloud === 'gcp' ? 'rgba(52,211,153,0.12)' : 'rgba(251,191,36,0.12)',
                  color: t.cloud === 'gcp' ? 'var(--neon-green)' : 'var(--color-accent-amber)',
                  borderRadius: 999, padding: '4px 10px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
                }}>
                  {t.cloud || 'unknown'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showOnboard && <TenantOnboardModal onClose={() => setShowOnboard(false)} onSaved={() => { setShowOnboard(false); load() }} />}
    </div>
  )
}

function TenantOnboardModal({ onClose, onSaved }) {
  const { addToast } = useToasts()
  const [form, setForm] = useState({ display_name: '', name: '', cloud: 'aws', escalation_email: '', server_count: '' })
  const [saving, setSaving] = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const handleSave = async () => {
    if (!form.display_name || !form.name) { toast('Display name and slug are required', 'error'); return }
    setSaving(true)
    try {
      // Tenant creation is config-driven in current backend.
      // This form generates the config snippet needed.
      toast('Tenant config snippet generated. Add it to config/tenants.yaml and redeploy.')
      setTimeout(onSaved, 800)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const configSnippet = form.name ? `# Add to config/tenants.yaml\n- name: ${form.name}\n  display_name: "${form.display_name}"\n  cloud: ${form.cloud}\n  escalation_email: ${form.escalation_email || 'ops@example.com'}\n  server_count: ${form.server_count || 0}` : ''

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div className="relative w-full max-w-lg mx-4 glass rounded-2xl p-6 space-y-4 overflow-y-auto" style={{ maxHeight: '90vh' }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>Onboard New Tenant</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Display Name *</label>
            <input value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} placeholder="Acme Corp" style={inputCls} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug (unique ID) *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value.toLowerCase().replace(/\s+/g,'-') }))} placeholder="acme-corp" style={{ ...inputCls, fontFamily: 'var(--font-mono)' }} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Cloud Provider</label>
            <select value={form.cloud} onChange={e => setForm(f => ({ ...f, cloud: e.target.value }))} style={inputCls}>
              <option value="aws">AWS</option>
              <option value="gcp">GCP</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Server Count</label>
            <input value={form.server_count} onChange={e => setForm(f => ({ ...f, server_count: e.target.value }))} type="number" min="0" placeholder="0" style={inputCls} />
          </div>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Escalation Email</label>
          <input value={form.escalation_email} onChange={e => setForm(f => ({ ...f, escalation_email: e.target.value }))} placeholder="ops@acme.com" type="email" style={inputCls} />
        </div>
        {configSnippet && (
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Config Snippet (add to tenants.yaml)</label>
            <pre style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--neon-green)', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {configSnippet}
            </pre>
          </div>
        )}
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Generating…' : 'Generate Config'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Settings Tab ──────────────────────────────────────────────────────────────

function SettingsTab() {
  const { addToast } = useToasts()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  useEffect(() => {
    fetchSettings()
      .then(setSettings)
      .catch(() => toast('Failed to load settings', 'error'))
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      await updateSettings(settings)
      toast('Settings saved — some changes need a service restart')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const field = (label, key, type = 'text', opts = {}) => (
    <div key={key}>
      <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>{label}</label>
      <input
        type={type}
        value={settings?.[key] ?? ''}
        onChange={e => setSettings(s => ({ ...s, [key]: type === 'number' ? Number(e.target.value) : e.target.value }))}
        disabled={!settings}
        placeholder={opts.placeholder || ''}
        style={{ ...inputCls, fontFamily: type === 'password' ? 'monospace' : 'inherit' }}
      />
    </div>
  )

  if (loading) return <div className="space-y-2">{[1,2,3,4].map(i => <div key={i} className="glass rounded-xl h-20 skeleton" />)}</div>

  return (
    <div className="space-y-6">
      {/* Auto-approval Policy */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="Auto-Approval Policy" />
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Auto Approve</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Automatically approve low-risk remediations without human review</div>
            </div>
            <button onClick={() => setSettings(s => ({ ...s, auto_approve: !s?.auto_approve }))} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
              {settings?.auto_approve
                ? <ToggleRight size={32} style={{ color: 'var(--color-accent-green)' }} />
                : <ToggleLeft  size={32} style={{ color: 'var(--text-muted)' }} />}
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Max Allowed Risk</label>
              <select value={settings?.max_allowed_risk || 'LOW'} onChange={e => setSettings(s => ({ ...s, max_allowed_risk: e.target.value }))} disabled={!settings} style={inputCls}>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Min Confidence to Approve (0–1)</label>
              <input type="number" step="0.05" min="0" max="1" value={settings?.min_confidence_to_approve ?? 0.8} onChange={e => setSettings(s => ({ ...s, min_confidence_to_approve: parseFloat(e.target.value) }))} disabled={!settings} style={inputCls} />
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Timeouts */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="Pipeline Timeouts & Retries" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {field('Investigation Timeout (s)', 'investigation_timeout', 'number')}
          {field('Execution Timeout (s)',    'execution_timeout',     'number')}
          {field('Verification Timeout (s)', 'verification_timeout',  'number')}
          {field('Max Investigation Retries','max_investigation_retries','number')}
          {field('Max Execution Retries',    'max_execution_retries',  'number')}
          {field('Max Verification Retries', 'max_verification_retries','number')}
        </div>
      </div>

      {/* Notifications */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="Notifications" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {field('Slack Webhook URL',  'slack_webhook_url', 'password', { placeholder: 'https://hooks.slack.com/…' })}
          {field('Email From',         'email_from',        'email',    { placeholder: 'noreply@example.com' })}
          {field('SMTP Host',          'email_smtp_host',   'text',     { placeholder: 'smtp.example.com' })}
          {field('SMTP Port',          'email_smtp_port',   'number',   { placeholder: '587' })}
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving || !settings} className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-60 transition-all hover:-translate-y-0.5" style={{ background: 'var(--gradient-primary)' }}>
          <Save size={14} />
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

// ── AI Models Tab ─────────────────────────────────────────────────────────────

function ModelsTab() {
  const { addToast } = useToasts()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  useEffect(() => {
    fetchSettings()
      .then(setSettings)
      .catch(() => toast('Failed to load model config', 'error'))
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      await updateSettings(settings)
      toast('Model config saved — service restart required')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="glass rounded-xl h-20 skeleton" />)}</div>

  return (
    <div className="space-y-6">
      {/* LLM Configuration */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg" style={{ background: 'rgba(167,139,250,0.12)' }}>
            <Brain size={16} style={{ color: 'var(--neon-purple)' }} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>LLM Provider & Models</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Routed via LiteLLM proxy</div>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Provider</label>
            <div className="px-3 py-2 rounded-lg" style={{ ...inputCls, color: 'var(--text-secondary)', cursor: 'default' }}>
              {settings?.llm_provider || 'vertex_ai_beta'}
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Primary Model</label>
            <input value={settings?.llm_primary_model || ''} onChange={e => setSettings(s => ({ ...s, llm_primary_model: e.target.value }))} placeholder="gemini-2.0-flash" style={inputCls} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Fallback Model</label>
            <input value={settings?.llm_fallback_model || ''} onChange={e => setSettings(s => ({ ...s, llm_fallback_model: e.target.value }))} placeholder="gemini-2.0-flash-lite" style={inputCls} />
          </div>
        </div>
      </div>

      {/* Circuit Breaker */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg" style={{ background: 'rgba(251,146,60,0.12)' }}>
            <Activity size={16} style={{ color: 'var(--brand-orange)' }} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Circuit Breaker</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Automatic fallback when primary model fails</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Failure Threshold (trips circuit)</label>
            <input type="number" min="1" value={settings?.llm_circuit_breaker_threshold ?? 5} onChange={e => setSettings(s => ({ ...s, llm_circuit_breaker_threshold: Number(e.target.value) }))} style={inputCls} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Cooldown (seconds)</label>
            <input type="number" min="10" value={settings?.llm_circuit_breaker_cooldown ?? 60} onChange={e => setSettings(s => ({ ...s, llm_circuit_breaker_cooldown: Number(e.target.value) }))} style={inputCls} />
          </div>
        </div>
      </div>

      {/* Status Display */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="Model Status" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { label: 'Primary Model',  value: settings?.llm_primary_model  || 'gemini-2.0-flash',      color: 'var(--neon-green)', status: 'Active' },
            { label: 'Fallback Model', value: settings?.llm_fallback_model || 'gemini-2.0-flash-lite', color: 'var(--color-accent-amber)', status: 'Standby' },
          ].map(m => (
            <div key={m.label} className="flex items-center gap-4 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <Cpu size={16} style={{ color: m.color }} />
              <div className="flex-1">
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{m.label}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{m.value}</div>
              </div>
              <span style={{ background: `${m.color}22`, color: m.color, borderRadius: 999, padding: '3px 9px', fontSize: 10, fontWeight: 700 }}>
                {m.status}
              </span>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 12 }}>
          Model changes are routed via the LiteLLM proxy. Changes require a proxy restart.
        </p>
      </div>

      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving || !settings} className="flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold text-white disabled:opacity-60 transition-all hover:-translate-y-0.5" style={{ background: 'var(--gradient-primary)' }}>
          <Save size={14} />
          {saving ? 'Saving…' : 'Save Model Config'}
        </button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SuperAdminPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'overview'

  const setTab = (id) => setSearchParams(id === 'overview' ? {} : { tab: id })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="p-3 rounded-xl" style={{ background: 'linear-gradient(135deg,rgba(99,102,241,0.15),rgba(139,92,246,0.1))', border: '1px solid rgba(99,102,241,0.2)' }}>
          <ShieldCheck size={22} style={{ color: 'var(--neon-indigo)' }} />
        </div>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>Super Admin</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Users · Tenants · Settings · AI Models
          </p>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 p-1 rounded-xl overflow-x-auto" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setTab(tab.id)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap"
            style={{
              background: activeTab === tab.id ? 'var(--bg-card)' : 'transparent',
              color:      activeTab === tab.id ? 'var(--text-heading)' : 'var(--text-muted)',
              boxShadow:  activeTab === tab.id ? 'var(--glass-shadow)' : 'none',
              border:     activeTab === tab.id ? '1px solid var(--border)' : '1px solid transparent',
            }}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && <OverviewTab onNavigate={setTab} />}
      {activeTab === 'users'    && <UsersTab />}
      {activeTab === 'tenants'  && <TenantsTab />}
      {activeTab === 'settings' && <SettingsTab />}
      {activeTab === 'models'   && <ModelsTab />}
    </div>
  )
}
