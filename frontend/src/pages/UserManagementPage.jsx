import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToasts } from '../context/ToastContext'
import { fetchUsers, createUser, updateUser, deleteUser } from '../services/api'
import { formatTimestamp, formatRelativeTime } from '../utils/formatters'
import { extractErrorMessage } from '../utils/errorHandler'
import { Users, Plus, Edit, Trash2, Shield, ShieldCheck, ShieldOff, Clock, Calendar } from 'lucide-react'

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

  const getRoleBadgeColor = (role) => {
    switch (role?.toLowerCase()) {
      case 'admin':
        return 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
      case 'operator':
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
      case 'viewer':
        return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
      default:
        return 'bg-gray-100 text-gray-700'
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
      <div className="flex items-center justify-between">
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
          className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
          style={{ fontSize: 13, fontWeight: 600, color: '#fff', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
        >
          <Plus size={16} />
          Create User
        </button>
      </div>

      <div className="glass rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="px-6 py-3 text-left text-sm font-semibold text-heading">User</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-heading">Role</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-heading">Status</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-heading">Created</th>
              <th className="px-6 py-3 text-right text-sm font-semibold text-heading">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-muted">
                  No users found
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="border-b border-border hover:bg-elevated transition-colors">
                  <td className="px-6 py-4">
                    <div>
                      <div className="font-medium">{u.display_name || u.email}</div>
                      <div className="text-sm text-muted">{u.email}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {getRoleIcon(u.role)}
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${getRoleBadgeColor(u.role)}`}>
                        {u.role?.toUpperCase() || 'OPERATOR'}
                      </span>
                      {u.id === currentUser?.userId && (
                        <span className="text-xs text-muted">(You)</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${u.is_active !== false
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                      }`}>
                      {u.is_active !== false ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
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
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setEditingUser(u)}
                        className="p-2 rounded-lg hover:bg-elevated transition-colors"
                        title="Edit user"
                      >
                        <Edit size={16} className="text-muted" />
                      </button>
                      {u.id !== currentUser?.userId && (
                        <button
                          onClick={() => handleDelete(u.id)}
                          className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
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
    password: '',
    display_name: user?.display_name || '',
    role: user?.role || 'operator',
    is_active: user?.is_active !== false,
  })

  const isSelf = user && currentUser && user.id === currentUser.userId
  const roleChanged = user && formData.role !== user.role

  const handleSubmit = (e) => {
    e.preventDefault()
    const data = { ...formData }
    if (user && !data.password) {
      delete data.password // Don't update password if not provided
    }
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
            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input
                type="password"
                required={!user}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              />
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
              <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
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
