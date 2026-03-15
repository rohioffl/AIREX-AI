import { useEffect, useMemo, useState } from 'react'
import {
  CalendarDays,
  CheckSquare,
  Clock3,
  Edit,
  Filter,
  Mail,
  Plus,
  RotateCcw,
  Search,
  Shield,
  ShieldCheck,
  ShieldOff,
  Square,
  Trash2,
  UserPlus,
  Users,
  X,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { useToasts } from '../context/ToastContext'
import { createUser, deleteUser, fetchUsers, resendInvitation, updateUser } from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'
import { formatRelativeTime, formatTimestamp } from '../utils/formatters'

function sectionStyle() {
  return {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 16,
    boxShadow: 'var(--glass-shadow)',
  }
}

function badgeStyle(bg, color) {
  return {
    background: bg,
    color,
    borderRadius: 999,
    padding: '4px 10px',
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: '0.02em',
  }
}

function roleMeta(role) {
  const normalized = (role || 'operator').toLowerCase()
  if (normalized === 'admin') {
    return {
      label: 'ADMIN',
      Icon: ShieldCheck,
      iconColor: '#c084fc',
      badge: badgeStyle('rgba(168, 85, 247, 0.16)', '#c084fc'),
    }
  }
  if (normalized === 'viewer') {
    return {
      label: 'VIEWER',
      Icon: ShieldOff,
      iconColor: '#94a3b8',
      badge: badgeStyle('rgba(148, 163, 184, 0.16)', '#94a3b8'),
    }
  }
  return {
    label: 'OPERATOR',
    Icon: Shield,
    iconColor: '#38bdf8',
    badge: badgeStyle('rgba(56, 189, 248, 0.16)', '#38bdf8'),
  }
}

function statusMeta(isActive) {
  return isActive
    ? badgeStyle('rgba(16, 185, 129, 0.16)', 'var(--neon-green)')
    : badgeStyle('rgba(244, 63, 94, 0.16)', 'var(--color-accent-red)')
}

function invitationMeta(status) {
  if (status === 'accepted') return badgeStyle('rgba(16, 185, 129, 0.16)', 'var(--neon-green)')
  if (status === 'expired') return badgeStyle('rgba(244, 63, 94, 0.16)', 'var(--color-accent-red)')
  return badgeStyle('rgba(245, 158, 11, 0.16)', '#fbbf24')
}

export default function UserManagementPage() {
  const { user: currentUser } = useAuth()
  const { isDark } = useTheme()
  const { addToast } = useToasts()

  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedUsers, setSelectedUsers] = useState(new Set())

  const showToast = (message, type) => {
    addToast({
      title: type === 'error' ? 'Error' : 'Success',
      message,
      severity: type === 'error' ? 'CRITICAL' : 'LOW',
    })
  }

  const loadUsers = async () => {
    try {
      setLoading(true)
      const data = await fetchUsers()
      setUsers(data.items || [])
    } catch (err) {
      console.error(err)
      showToast('Failed to load users', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load on mount only
  }, [])

  const stats = useMemo(() => {
    const total = users.length
    const active = users.filter((u) => u.is_active !== false).length
    const pending = users.filter((u) => u.invitation_status === 'pending').length
    const admins = users.filter((u) => (u.role || '').toLowerCase() === 'admin').length
    return { total, active, pending, admins }
  }, [users])

  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const query = searchQuery.toLowerCase()
      const matchesSearch = !query ||
        u.email?.toLowerCase().includes(query) ||
        u.display_name?.toLowerCase().includes(query)

      const matchesRole = roleFilter === 'all' || (u.role || '').toLowerCase() === roleFilter
      const matchesStatus = statusFilter === 'all' ||
        (statusFilter === 'active' && u.is_active !== false) ||
        (statusFilter === 'inactive' && u.is_active === false) ||
        (statusFilter === 'pending' && u.invitation_status === 'pending')

      return matchesSearch && matchesRole && matchesStatus
    })
  }, [users, searchQuery, roleFilter, statusFilter])

  const clearFilters = () => {
    setSearchQuery('')
    setRoleFilter('all')
    setStatusFilter('all')
  }

  const handleCreate = async (formData) => {
    try {
      await createUser(formData)
      showToast('User created successfully', 'success')
      setShowCreateModal(false)
      loadUsers()
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Failed to create user', 'error')
    }
  }

  const handleUpdate = async (userId, formData) => {
    try {
      await updateUser(userId, formData)
      const roleChanged = editingUser && formData.role && formData.role !== editingUser.role
      showToast(roleChanged ? `Role updated to ${formData.role.toUpperCase()}` : 'User updated successfully', 'success')
      setEditingUser(null)
      loadUsers()
    } catch (err) {
      const errorMsg = extractErrorMessage(err) || 'Failed to update user'
      showToast(errorMsg, 'error')
      if (!errorMsg.includes('own')) {
        setEditingUser(null)
      }
    }
  }

  const handleDelete = async (userId) => {
    if (!confirm('Are you sure you want to deactivate this user?')) return
    try {
      await deleteUser(userId)
      showToast('User deactivated successfully', 'success')
      loadUsers()
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Failed to deactivate user', 'error')
    }
  }

  const handleSelectAll = () => {
    if (selectedUsers.size === filteredUsers.length) {
      setSelectedUsers(new Set())
      return
    }
    setSelectedUsers(new Set(filteredUsers.map((u) => u.id)))
  }

  const handleSelectUser = (userId) => {
    setSelectedUsers((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  const handleBulkActivate = async () => {
    if (!confirm(`Activate ${selectedUsers.size} user(s)?`)) return
    try {
      for (const userId of selectedUsers) {
        await updateUser(userId, { is_active: true })
      }
      showToast(`${selectedUsers.size} user(s) activated`, 'success')
      setSelectedUsers(new Set())
      loadUsers()
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Failed to activate users', 'error')
    }
  }

  const handleBulkDeactivate = async () => {
    if (!confirm(`Deactivate ${selectedUsers.size} user(s)?`)) return
    try {
      for (const userId of selectedUsers) {
        if (userId !== currentUser?.userId) {
          await updateUser(userId, { is_active: false })
        }
      }
      showToast(`${selectedUsers.size} user(s) deactivated`, 'success')
      setSelectedUsers(new Set())
      loadUsers()
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Failed to deactivate users', 'error')
    }
  }

  const headerGradient = isDark
    ? 'linear-gradient(135deg, rgba(99,102,241,0.16), rgba(34,211,238,0.1))'
    : 'linear-gradient(135deg, #e8f0ff, #ecfeff)'

  if (loading) {
    return (
      <div className="flex min-h-[320px] items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--text-heading)' }} />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <section style={{ ...sectionStyle(), padding: 20, background: headerGradient }}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold" style={{ color: 'var(--text-heading)' }}>
              <Users size={24} style={{ color: isDark ? '#a5b4fc' : '#2563eb' }} />
              User Access Control
            </h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
              Refined user administration for clear light/dark visual separation.
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white transition"
            style={{
              background: isDark ? 'var(--gradient-primary)' : 'linear-gradient(135deg,#2563eb,#06b6d4)',
              boxShadow: isDark ? '0 10px 24px rgba(99,102,241,0.35)' : '0 8px 18px rgba(37,99,235,0.28)',
            }}
          >
            <UserPlus size={16} />
            New user
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard label="Total" value={stats.total} accent="#818cf8" />
          <StatCard label="Active" value={stats.active} accent="#10b981" />
          <StatCard label="Pending" value={stats.pending} accent="#f59e0b" />
          <StatCard label="Admins" value={stats.admins} accent="#a855f7" />
        </div>
      </section>

      <section style={{ ...sectionStyle(), padding: 16 }}>
        <div className="flex flex-col gap-3 lg:flex-row">
          <div className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <Search size={16} style={{ color: 'var(--text-muted)' }} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by email or name"
              className="w-full bg-transparent text-sm outline-none"
              style={{ color: 'var(--text-primary)' }}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="rounded p-1" style={{ color: 'var(--text-muted)' }}>
                <X size={14} />
              </button>
            )}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="inline-flex items-center gap-2 rounded-lg px-3 py-2" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <Filter size={14} style={{ color: 'var(--text-muted)' }} />
              <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="bg-transparent text-sm outline-none" style={{ color: 'var(--text-primary)' }}>
                <option value="all">All roles</option>
                <option value="admin">Admin</option>
                <option value="operator">Operator</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>

            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg px-3 py-2 text-sm outline-none" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}>
              <option value="all">All status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="pending">Pending invitation</option>
            </select>

            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            >
              <RotateCcw size={14} /> Reset
            </button>
          </div>
        </div>

        {selectedUsers.size > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg p-3" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{selectedUsers.size} selected</span>
            <button onClick={handleBulkActivate} className="rounded-md px-3 py-1.5 text-xs font-semibold text-white" style={{ background: 'var(--neon-green)' }}>Activate</button>
            <button onClick={handleBulkDeactivate} className="rounded-md px-3 py-1.5 text-xs font-semibold text-white" style={{ background: '#dc2626' }}>Deactivate</button>
            <button
              onClick={() => setSelectedUsers(new Set())}
              className="rounded-md px-3 py-1.5 text-xs font-semibold"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            >
              Clear
            </button>
          </div>
        )}
      </section>

      <section style={{ ...sectionStyle(), overflow: 'hidden' }}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px]">
            <thead>
              <tr style={{ background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border)' }}>
                <th className="px-4 py-3 text-left">
                  <button onClick={handleSelectAll} className="rounded p-1" style={{ color: 'var(--text-muted)' }}>
                    {selectedUsers.size === filteredUsers.length && filteredUsers.length > 0 ? <CheckSquare size={18} /> : <Square size={18} />}
                  </button>
                </th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>User</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Role</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Status</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Invitation</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Created</th>
                <th className="px-4 py-3 text-right text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {users.length === 0 ? 'No users found' : 'No users match current filters'}
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const role = roleMeta(u.role)
                  const isActive = u.is_active !== false
                  return (
                    <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td className="px-4 py-3">
                        <button onClick={() => handleSelectUser(u.id)} className="rounded p-1" style={{ color: 'var(--text-muted)' }}>
                          {selectedUsers.has(u.id) ? <CheckSquare size={18} /> : <Square size={18} />}
                        </button>
                      </td>

                      <td className="px-4 py-3">
                        <div>
                          <div className="text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>
                            {u.display_name || u.email}
                            {u.id === currentUser?.userId && <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>(You)</span>}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{u.email}</div>
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <role.Icon size={14} style={{ color: role.iconColor }} />
                          <span style={role.badge}>{role.label}</span>
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        <span style={statusMeta(isActive)}>{isActive ? 'ACTIVE' : 'INACTIVE'}</span>
                      </td>

                      <td className="px-4 py-3">
                        {u.invitation_status ? (
                          <div className="space-y-1">
                            <span style={invitationMeta(u.invitation_status)}>{u.invitation_status.toUpperCase()}</span>
                            {u.invitation_status === 'pending' && u.invitation_expires_at && (
                              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                Expires {formatRelativeTime(u.invitation_expires_at)}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>-</span>
                        )}
                      </td>

                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {u.created_at ? (
                          <div className="space-y-1">
                            <div className="inline-flex items-center gap-1"><CalendarDays size={12} /> {formatTimestamp(u.created_at)}</div>
                            {u.updated_at && u.updated_at !== u.created_at && (
                              <div className="inline-flex items-center gap-1"><Clock3 size={12} /> Updated {formatRelativeTime(u.updated_at)}</div>
                            )}
                          </div>
                        ) : '-'}
                      </td>

                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          {u.invitation_status === 'pending' && (
                            <button
                              onClick={async () => {
                                try {
                                  await resendInvitation(u.id)
                                  showToast('Invitation resent successfully', 'success')
                                  loadUsers()
                                } catch (err) {
                                  showToast(extractErrorMessage(err) || 'Failed to resend invitation', 'error')
                                }
                              }}
                              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold"
                              style={{ background: 'var(--glow-sky)', color: 'var(--neon-cyan)' }}
                              title="Resend invitation"
                            >
                              <Mail size={12} /> Resend
                            </button>
                          )}

                          <button
                            onClick={() => setEditingUser(u)}
                            className="rounded-md p-2"
                            style={{ color: 'var(--text-secondary)', background: 'transparent' }}
                            title="Edit user"
                          >
                            <Edit size={15} />
                          </button>

                          {u.id !== currentUser?.userId && (
                            <button
                              onClick={() => handleDelete(u.id)}
                              className="rounded-md p-2"
                              style={{ color: 'var(--color-accent-red)', background: 'transparent' }}
                              title="Deactivate user"
                            >
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {showCreateModal && <UserModal onClose={() => setShowCreateModal(false)} onSave={handleCreate} />}
      {editingUser && (
        <UserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={(data) => handleUpdate(editingUser.id, data)}
        />
      )}
    </div>
  )
}

function StatCard({ label, value, accent }) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: `1px solid ${accent}33`,
        borderRadius: 12,
        padding: 12,
      }}
    >
      <div className="text-xs font-semibold uppercase" style={{ color: 'var(--text-secondary)', letterSpacing: '0.08em' }}>{label}</div>
      <div className="mt-1 text-2xl font-bold" style={{ color: accent }}>{value}</div>
    </div>
  )
}

function UserModal({ user, onClose, onSave }) {
  const { user: currentUser } = useAuth()
  const { isDark } = useTheme()

  const [formData, setFormData] = useState({
    email: user?.email || '',
    display_name: user?.display_name || '',
    role: user?.role || 'operator',
    is_active: user?.is_active !== false,
  })

  const isSelf = user && currentUser && user.id === currentUser.userId
  const roleChanged = user && formData.role !== user.role

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave({ ...formData })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-2xl p-5"
        style={{
          background: isDark ? 'linear-gradient(160deg, rgba(17,19,24,0.96), rgba(12,15,23,0.96))' : 'linear-gradient(160deg, #ffffff, #f2f8ff)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--glass-shadow)',
        }}
      >
        <h2 className="mb-4 flex items-center gap-2 text-lg font-bold" style={{ color: 'var(--text-heading)' }}>
          {user ? <Edit size={16} /> : <Plus size={16} />}
          {user ? 'Edit user' : 'Create user'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Email">
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              disabled={Boolean(user)}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </Field>

          {!user && (
            <div className="rounded-lg p-3 text-sm" style={{ background: 'var(--glow-sky)', border: '1px solid rgba(56,189,248,0.25)', color: 'var(--neon-cyan)' }}>
              An invitation email will be sent. The user sets password from that link.
            </div>
          )}

          <Field label="Display name">
            <input
              type="text"
              required
              value={formData.display_name}
              onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </Field>

          <Field label={isSelf ? 'Role (cannot change your own role)' : 'Role'}>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              disabled={isSelf}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            >
              <option value="viewer">Viewer (read-only)</option>
              <option value="operator">Operator (incident actions)</option>
              <option value="admin">Admin (full access + users)</option>
            </select>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
              {formData.role === 'viewer' && 'Can view incidents and dashboards only.'}
              {formData.role === 'operator' && 'Can triage incidents and execute approved actions.'}
              {formData.role === 'admin' && 'Full platform access including administration.'}
            </p>
            {roleChanged && !isSelf && (
              <p className="mt-1 text-xs" style={{ color: 'var(--color-accent-amber)' }}>
                Role will change from {user.role.toUpperCase()} to {formData.role.toUpperCase()}.
              </p>
            )}
          </Field>

          {user && (
            <label className="inline-flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Active user
            </label>
          )}

          <div className="flex items-center justify-end gap-2 border-t pt-4" style={{ borderColor: 'var(--border)' }}>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-semibold"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-lg px-4 py-2 text-sm font-semibold text-white"
              style={{ background: isDark ? 'var(--gradient-primary)' : 'linear-gradient(135deg,#2563eb,#06b6d4)' }}
            >
              {user ? 'Update user' : 'Create user'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-semibold" style={{ color: 'var(--text-heading)' }}>{label}</label>
      {children}
    </div>
  )
}
