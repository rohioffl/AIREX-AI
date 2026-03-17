import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckCircle,
  Clock,
  Edit,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  Trash2,
  Users,
  X,
  XCircle,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToasts } from '../../context/ToastContext'
import {
  createUser,
  deleteUser,
  fetchUsers,
  resendInvitation,
  updateUser,
} from '../../services/api'
import { extractErrorMessage } from '../../utils/errorHandler'
import { formatRelativeTime } from '../../utils/formatters'

// ── Helpers ───────────────────────────────────────────────────────────────────

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

function roleMeta(role) {
  const r = (role || 'operator').toLowerCase()
  if (r === 'admin')  return { label: 'ADMIN',    color: 'var(--neon-purple)', bg: 'rgba(192,132,252,0.12)' }
  if (r === 'viewer') return { label: 'VIEWER',   color: 'var(--text-muted)',  bg: 'rgba(148,163,184,0.12)' }
  return                     { label: 'OPERATOR', color: 'var(--neon-cyan)',   bg: 'rgba(56,189,248,0.12)' }
}

function RoleBadge({ role }) {
  const m = roleMeta(role)
  return (
    <span style={{ background: m.bg, color: m.color, borderRadius: 999, padding: '3px 9px', fontSize: 11, fontWeight: 700 }}>
      {m.label}
    </span>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function UsersAdminPage() {
  const { user: currentUser } = useAuth()
  const { addToast } = useToasts()
  const [users,      setUsers]      = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editUser,   setEditUser]   = useState(null)

  const toast = useCallback(
    (msg, type = 'success') =>
      addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' }),
    [addToast]
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
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
    total:   users.length,
    active:  users.filter(u => u.is_active !== false).length,
    admins:  users.filter(u => (u.role || '').toLowerCase() === 'admin').length,
    pending: users.filter(u => u.invitation_status === 'pending').length,
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

  const handleResend = async (u) => {
    try {
      await resendInvitation(u.id)
      toast('Invite resent')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Resend failed', 'error')
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            User Management
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Manage user accounts, roles, and invitations across the platform.
          </p>
        </div>
        <Link
          to="/admin"
          className="px-4 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          Back to Admin
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Users"    value={stats.total}   color="var(--neon-indigo)"        icon={Users} />
        <StatCard label="Active"         value={stats.active}  color="var(--neon-green)"          icon={CheckCircle} />
        <StatCard label="Admins"         value={stats.admins}  color="var(--neon-purple)"         icon={ShieldCheck} />
        <StatCard label="Pending Invite" value={stats.pending} color="var(--color-accent-amber)" icon={Clock} />
      </div>

      {/* Toolbar */}
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
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white"
          style={{ background: 'var(--gradient-primary)' }}
        >
          <Plus size={13} /> Add User
        </button>
        <button onClick={load} className="p-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <RefreshCcw size={13} style={{ color: 'var(--text-muted)' }} />
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">{[1, 2, 3, 4, 5].map(i => <div key={i} className="glass rounded-xl h-14 skeleton" />)}</div>
      ) : (
        <div className="glass rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
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
                <tr><td colSpan={6} style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>No users found</td></tr>
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
                      <div className="flex items-center gap-2">
                        <span style={{
                          background: u.invitation_status === 'accepted' ? 'rgba(52,211,153,0.12)' : 'rgba(251,191,36,0.12)',
                          color: u.invitation_status === 'accepted' ? 'var(--neon-green)' : 'var(--color-accent-amber)',
                          borderRadius: 999, padding: '3px 9px', fontSize: 11, fontWeight: 700,
                        }}>
                          {u.invitation_status}
                        </span>
                        {u.invitation_status === 'pending' && (
                          <button
                            onClick={() => handleResend(u)}
                            style={{ fontSize: 10, color: 'var(--neon-indigo)', textDecoration: 'underline', cursor: 'pointer', background: 'none', border: 'none' }}
                          >
                            Resend
                          </button>
                        )}
                      </div>
                    ) : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: 'var(--text-muted)' }}>
                    {u.last_login_at ? formatRelativeTime(u.last_login_at) : '—'}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <div className="flex items-center gap-2">
                      <button onClick={() => setEditUser(u)} className="p-1.5 rounded" style={{ color: 'var(--neon-indigo)', background: 'var(--glow-indigo)' }} title="Edit">
                        <Edit size={12} />
                      </button>
                      <button onClick={() => handleToggleActive(u)} className="p-1.5 rounded" style={{ color: u.is_active !== false ? 'var(--color-accent-red)' : 'var(--neon-green)', background: 'var(--bg-input)' }} title={u.is_active !== false ? 'Deactivate' : 'Activate'}>
                        {u.is_active !== false ? <XCircle size={12} /> : <CheckCircle size={12} />}
                      </button>
                      {u.id !== currentUser?.user_id && (
                        <button onClick={() => handleDelete(u.id, u.email)} className="p-1.5 rounded" style={{ color: 'var(--color-accent-red)', background: 'var(--glow-rose)' }} title="Remove">
                          <Trash2 size={12} />
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

      {(showCreate || editUser) && (
        <UserModal
          user={editUser}
          onClose={() => { setShowCreate(false); setEditUser(null) }}
          onSaved={() => { setShowCreate(false); setEditUser(null); load() }}
          toast={toast}
        />
      )}
    </div>
  )
}

// ── User Modal ────────────────────────────────────────────────────────────────

function UserModal({ user, onClose, onSaved, toast }) {
  const [form, setForm] = useState({
    email:        user?.email        || '',
    display_name: user?.display_name || '',
    role:         user?.role         || 'operator',
    password:     '',
  })
  const [saving, setSaving] = useState(false)

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
