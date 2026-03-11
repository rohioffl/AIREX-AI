import { useState, useEffect, useMemo } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToasts } from '../context/ToastContext'
import { fetchUsers, createUser, updateUser, deleteUser, resendInvitation } from '../services/api'
import { formatTimestamp, formatRelativeTime } from '../utils/formatters'
import { extractErrorMessage } from '../utils/errorHandler'
import { Users, Plus, Edit, Trash2, Shield, ShieldCheck, ShieldOff, Clock, Calendar, Search, X, CheckSquare, Square } from 'lucide-react'

export default function UserManagementPage() {
  const { user: currentUser } = useAuth()
  const { addToast } = useToasts()
  const showToast = (message, type) => {
    addToast({ title: type === 'error' ? 'Error' : 'Success', message, severity: type === 'error' ? 'CRITICAL' : 'LOW' })
  }
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedUsers, setSelectedUsers] = useState(new Set())

  useEffect(() => {
    loadUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadUsers only needed on mount
  }, [])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const data = await fetchUsers()
      setUsers(data.items || [])
    } catch (err) {
      showToast('Failed to load users', 'error')
      console.error(err)
    } finally {
      setLoading(false)
    }
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
      showToast(
        roleChanged
          ? `User role updated to ${formData.role.toUpperCase()} successfully`
          : 'User updated successfully',
        'success'
      )
      setEditingUser(null)
      loadUsers()
    } catch (err) {
      const errorMsg = extractErrorMessage(err) || 'Failed to update user'
      showToast(errorMsg, 'error')
      // If it's a self-modification error, keep the modal open
      if (errorMsg.includes('own')) {
        // Modal stays open so user can see the error
      } else {
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

  const getRoleIcon = (role) => {
    switch (role?.toLowerCase()) {
      case 'admin':
        return <ShieldCheck size={16} className="text-purple-500" />
      case 'operator':
        return <Shield size={16} className="text-blue-500" />
      case 'viewer':
        return <ShieldOff size={16} className="text-gray-500" />
      default:
        return <Shield size={16} />
    }
  }

  const getRoleBadgeStyle = (role) => {
    switch (role?.toLowerCase()) {
      case 'admin':
        return { background: 'rgba(168,85,247,0.15)', color: '#c084fc' }
      case 'operator':
        return { background: 'rgba(59,130,246,0.15)', color: '#93c5fd' }
      case 'viewer':
        return { background: 'rgba(148,163,184,0.1)', color: '#cbd5e1' }
      default:
        return { background: 'rgba(148,163,184,0.1)', color: '#cbd5e1' }
    }
  }

  // Filter users
  const filteredUsers = useMemo(() => {
    return users.filter(u => {
      const matchesSearch = !searchQuery || 
        u.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.display_name?.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesRole = roleFilter === 'all' || u.role?.toLowerCase() === roleFilter.toLowerCase()
      const matchesStatus = statusFilter === 'all' || 
        (statusFilter === 'active' && u.is_active !== false) ||
        (statusFilter === 'inactive' && u.is_active === false) ||
        (statusFilter === 'pending' && u.invitation_status === 'pending')
      return matchesSearch && matchesRole && matchesStatus
    })
  }, [users, searchQuery, roleFilter, statusFilter])

  const handleSelectAll = () => {
    if (selectedUsers.size === filteredUsers.length) {
      setSelectedUsers(new Set())
    } else {
      setSelectedUsers(new Set(filteredUsers.map(u => u.id)))
    }
  }

  const handleSelectUser = (userId) => {
    setSelectedUsers(prev => {
      const next = new Set(prev)
      if (next.has(userId)) {
        next.delete(userId)
      } else {
        next.add(userId)
      }
      return next
    })
  }

  const handleBulkActivate = async () => {
    if (!confirm(`Activate ${selectedUsers.size} user(s)?`)) return
    try {
      for (const userId of selectedUsers) {
        await updateUser(userId, { is_active: true })
      }
      showToast(`${selectedUsers.size} user(s) activated successfully`, 'success')
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
      showToast(`${selectedUsers.size} user(s) deactivated successfully`, 'success')
      setSelectedUsers(new Set())
      loadUsers()
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Failed to deactivate users', 'error')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <Users size={24} style={{ color: '#94a3b8' }} />
            User Management
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Manage user accounts and permissions
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all touch-manipulation"
          style={{ fontSize: 13, fontWeight: 600, color: '#fff', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', minHeight: 44 }}
        >
          <Plus size={16} />
          Create User
        </button>
      </div>

      {/* Search and Filters */}
      <div className="glass rounded-xl p-4 space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <Search size={16} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search by email or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent border-none outline-none"
              style={{ color: 'var(--text-primary)', fontSize: 13 }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="p-1 rounded hover:bg-elevated transition-colors"
                style={{ minWidth: 32, minHeight: 32 }}
              >
                <X size={14} style={{ color: 'var(--text-muted)' }} />
              </button>
            )}
          </div>

          {/* Role Filter */}
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-input text-text-primary touch-manipulation"
            style={{ fontSize: 13, minHeight: 44 }}
          >
            <option value="all">All Roles</option>
            <option value="admin">Admin</option>
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-input text-text-primary touch-manipulation"
            style={{ fontSize: 13, minHeight: 44 }}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="pending">Pending Invitation</option>
          </select>
        </div>

        {/* Bulk Actions */}
        {selectedUsers.size > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-border">
            <span className="text-sm text-muted">
              {selectedUsers.size} user(s) selected
            </span>
            <button
              onClick={handleBulkActivate}
              className="px-3 py-1.5 rounded text-xs font-semibold transition-colors touch-manipulation"
              style={{ background: 'rgba(16,185,129,0.15)', color: '#6ee7b7', minHeight: 36 }}
            >
              Activate
            </button>
            <button
              onClick={handleBulkDeactivate}
              className="px-3 py-1.5 rounded text-xs font-semibold transition-colors touch-manipulation"
              style={{ background: 'rgba(244,63,94,0.15)', color: '#fda4af', minHeight: 36 }}
            >
              Deactivate
            </button>
            <button
              onClick={() => setSelectedUsers(new Set())}
              className="px-3 py-1.5 rounded text-xs font-semibold transition-colors touch-manipulation"
              style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)', minHeight: 36 }}
            >
              Clear
            </button>
          </div>
        )}
      </div>

      <div className="glass rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 sm:px-6 py-3 text-left">
                  <button
                    onClick={handleSelectAll}
                    className="p-1 rounded hover:bg-elevated transition-colors touch-manipulation"
                    style={{ minWidth: 32, minHeight: 32 }}
                    title="Select all"
                  >
                    {selectedUsers.size === filteredUsers.length && filteredUsers.length > 0 ? (
                      <CheckSquare size={18} style={{ color: '#6366f1' }} />
                    ) : (
                      <Square size={18} style={{ color: 'var(--text-muted)' }} />
                    )}
                  </button>
                </th>
                <th className="px-4 sm:px-6 py-3 text-left text-sm font-semibold text-heading">User</th>
                <th className="px-4 sm:px-6 py-3 text-left text-sm font-semibold text-heading hidden sm:table-cell">Role</th>
                <th className="px-4 sm:px-6 py-3 text-left text-sm font-semibold text-heading">Status</th>
                <th className="px-4 sm:px-6 py-3 text-left text-sm font-semibold text-heading hidden lg:table-cell">Invitation</th>
                <th className="px-4 sm:px-6 py-3 text-left text-sm font-semibold text-heading hidden md:table-cell">Created</th>
                <th className="px-4 sm:px-6 py-3 text-right text-sm font-semibold text-heading">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-muted">
                    {users.length === 0 ? 'No users found' : 'No users match your filters'}
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                <tr key={u.id} className="border-b border-border hover:bg-elevated transition-colors">
                  <td className="px-4 sm:px-6 py-4">
                    <button
                      onClick={() => handleSelectUser(u.id)}
                      className="p-1 rounded hover:bg-elevated transition-colors touch-manipulation"
                      style={{ minWidth: 32, minHeight: 32 }}
                    >
                      {selectedUsers.has(u.id) ? (
                        <CheckSquare size={18} style={{ color: '#6366f1' }} />
                      ) : (
                        <Square size={18} style={{ color: 'var(--text-muted)' }} />
                      )}
                    </button>
                  </td>
                  <td className="px-4 sm:px-6 py-4">
                    <div>
                      <div className="font-medium">{u.display_name || u.email}</div>
                      <div className="text-sm text-muted">{u.email}</div>
                      {/* Mobile: Show role badge */}
                      <div className="sm:hidden mt-2 flex items-center gap-2">
                        {getRoleIcon(u.role)}
                        <span className="px-2 py-1 rounded text-xs font-semibold" style={getRoleBadgeStyle(u.role)}>
                          {u.role?.toUpperCase() || 'OPERATOR'}
                        </span>
                        {u.id === currentUser?.userId && (
                          <span className="text-xs text-muted">(You)</span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 sm:px-6 py-4 hidden sm:table-cell">
                    <div className="flex items-center gap-2">
                      {getRoleIcon(u.role)}
                      <span className="px-2 py-1 rounded text-xs font-semibold" style={getRoleBadgeStyle(u.role)}>
                        {u.role?.toUpperCase() || 'OPERATOR'}
                      </span>
                      {u.id === currentUser?.userId && (
                        <span className="text-xs text-muted">(You)</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 sm:px-6 py-4">
                    <div className="flex flex-col gap-1">
                      <span
                        className="px-2 py-1 rounded text-xs font-semibold inline-block w-fit"
                        style={u.is_active !== false
                          ? { background: 'rgba(16,185,129,0.15)', color: '#6ee7b7' }
                          : { background: 'rgba(244,63,94,0.15)', color: '#fda4af' }
                        }
                      >
                        {u.is_active !== false ? 'Active' : 'Inactive'}
                      </span>
                      {/* Mobile: Show invitation status */}
                      <div className="sm:hidden">
                        {u.invitation_status === 'pending' && (
                          <span className="px-2 py-1 rounded text-xs font-semibold inline-block mt-1" style={{ background: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24' }}>
                            Pending
                          </span>
                        )}
                        {u.invitation_status === 'accepted' && (
                          <span className="px-2 py-1 rounded text-xs font-semibold inline-block mt-1" style={{ background: 'rgba(16,185,129,0.15)', color: '#6ee7b7' }}>
                            Accepted
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 sm:px-6 py-4 hidden lg:table-cell">
                    {u.invitation_status === 'pending' && (
                      <div className="flex flex-col gap-1">
                        <span className="px-2 py-1 rounded text-xs font-semibold" style={{ background: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24' }}>
                          Pending
                        </span>
                        {u.invitation_expires_at && (
                          <span className="text-xs text-muted">
                            Expires {formatRelativeTime(u.invitation_expires_at)}
                          </span>
                        )}
                      </div>
                    )}
                    {u.invitation_status === 'accepted' && (
                      <span className="px-2 py-1 rounded text-xs font-semibold" style={{ background: 'rgba(16,185,129,0.15)', color: '#6ee7b7' }}>
                        Accepted
                      </span>
                    )}
                    {u.invitation_status === 'expired' && (
                      <span className="px-2 py-1 rounded text-xs font-semibold" style={{ background: 'rgba(244,63,94,0.15)', color: '#fda4af' }}>
                        Expired
                      </span>
                    )}
                    {!u.invitation_status && (
                      <span className="text-xs text-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 sm:px-6 py-4 hidden md:table-cell">
                    {u.created_at ? (
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-1 text-xs text-muted">
                          <Calendar size={12} />
                          {formatTimestamp(u.created_at)}
                        </div>
                        {u.updated_at && u.updated_at !== u.created_at && (
                          <div className="flex items-center gap-1 text-xs text-muted">
                            <Clock size={12} />
                            Updated {formatRelativeTime(u.updated_at)}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted">—</span>
                    )}
                  </td>
                  <td className="px-4 sm:px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
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
                          className="px-2 sm:px-3 py-1 rounded text-xs font-semibold transition-colors touch-manipulation"
                          style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', minHeight: 32 }}
                          title="Resend invitation"
                        >
                          <span className="hidden sm:inline">Resend</span>
                          <span className="sm:hidden">↻</span>
                        </button>
                      )}
                      <button
                        onClick={() => setEditingUser(u)}
                        className="p-2 rounded-lg hover:bg-elevated transition-colors touch-manipulation"
                        style={{ minWidth: 36, minHeight: 36 }}
                        title="Edit user"
                      >
                        <Edit size={16} className="text-muted" />
                      </button>
                      {u.id !== currentUser?.userId && (
                        <button
                          onClick={() => handleDelete(u.id)}
                          className="p-2 rounded-lg transition-colors touch-manipulation"
                          style={{ minWidth: 36, minHeight: 36 }}
                          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(244,63,94,0.1)'}
                          onMouseLeave={(e) => e.currentTarget.style.background = ''}
                          title="Deactivate user"
                        >
                          <Trash2 size={16} className="text-red-500" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
      </div>

      {showCreateModal && (
        <UserModal
          onClose={() => setShowCreateModal(false)}
          onSave={handleCreate}
        />
      )}

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

function UserModal({ user, onClose, onSave }) {
  const { user: currentUser } = useAuth()
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
    const data = { ...formData }
    // Password is not needed for invitation flow
    onSave(data)
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in" onClick={onClose} style={{ animationDuration: '0.2s' }}>
      <div
        className="glass rounded-xl p-6 w-full max-w-md shadow-2xl border border-border/50 scale-100 transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="flex items-center gap-2 mb-5" style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>
          {user ? <Edit size={18} style={{ color: '#8b5cf6' }} /> : <Plus size={18} style={{ color: '#34d399' }} />}
          {user ? 'Edit User' : 'Create User'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              disabled={!!user}
            />
          </div>
          {!user && (
            <div className="p-3 rounded-lg" style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
              <p className="text-sm" style={{ color: '#3b82f6' }}>
                ℹ️ An invitation email will be sent to the user. They can set their password via the invitation link.
              </p>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium mb-1">Display Name</label>
            <input
              type="text"
              required
              value={formData.display_name}
              onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Role
              {isSelf && <span className="text-xs text-muted ml-2">(Cannot change your own role)</span>}
            </label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              disabled={isSelf}
            >
              <option value="viewer">Viewer (Read-only)</option>
              <option value="operator">Operator (Approve/Reject incidents)</option>
              <option value="admin">Admin (Full access + User management)</option>
            </select>
            <p className="text-xs text-muted mt-1">
              {formData.role === 'viewer' && 'Can only view incidents, no actions allowed'}
              {formData.role === 'operator' && 'Can approve/reject incidents and view all data'}
              {formData.role === 'admin' && 'Full access including user management and system settings'}
            </p>
            {roleChanged && !isSelf && (
              <p className="text-xs mt-1" style={{ color: '#fbbf24' }}>
                ⚠️ Role will be changed from {user.role.toUpperCase()} to {formData.role.toUpperCase()}
              </p>
            )}
          </div>
          {user && (
            <div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                <span className="text-sm">Active</span>
              </label>
            </div>
          )}
          <div className="flex gap-2 justify-end pt-4" style={{ borderTop: '1px solid var(--border)' }}>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg transition-colors hover:bg-elevated"
              style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg transition-all"
              style={{ fontSize: 13, fontWeight: 600, color: '#fff', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              {user ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
