import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Mail, Plus, RefreshCw, Trash2, Users, X } from 'lucide-react'

import { useToasts } from '../../context/ToastContext'
import {
  addTenantMember,
  fetchTenantMembers,
  fetchUsers,
  inviteTenantUser,
  removeTenantMember,
  updateTenantMember,
} from '../../services/api'
import { extractErrorMessage } from '../../utils/errorHandler'
import InviteTenantUserModal from './InviteTenantUserModal'

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

const TENANT_ROLE_OPTIONS = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'operator', label: 'Operator' },
  { value: 'admin', label: 'Admin' },
]

function AddMemberModal({ nonMembers, onClose, onAdd }) {
  const [addUserId, setAddUserId] = useState('')
  const [addRole, setAddRole] = useState('viewer')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!addUserId) return
    setSaving(true)
    await onAdd(addUserId, addRole)
    setSaving(false)
    onClose()
  }

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 12, width: '100%', maxWidth: 420, padding: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
            Add Member
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>User</label>
            <select
              aria-label="Tenant member user"
              value={addUserId}
              onChange={(e) => setAddUserId(e.target.value)}
              style={inputCls}
            >
              <option value="">Select a user…</option>
              {nonMembers.map((user) => (
                <option key={user.id} value={user.id}>{user.display_name || user.email}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Role</label>
            <select
              aria-label="Tenant member role"
              value={addRole}
              onChange={(e) => setAddRole(e.target.value)}
              style={inputCls}
            >
              {TENANT_ROLE_OPTIONS.map((role) => (
                <option key={role.value} value={role.value}>{role.label}</option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 4 }}>
            <button
              type="button"
              onClick={onClose}
              style={{ padding: '8px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!addUserId || saving}
              style={{
                padding: '8px 18px', borderRadius: 6, border: 'none',
                background: !addUserId || saving ? 'var(--border)' : 'var(--neon-cyan)',
                color: !addUserId || saving ? 'var(--text-muted)' : '#000',
                fontSize: 13, fontWeight: 600,
                cursor: !addUserId || saving ? 'not-allowed' : 'pointer',
              }}
            >
              {saving ? 'Adding…' : 'Add Member'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

export default function TenantMembersPanel({ tenant }) {
  const { addToast } = useToasts()
  const [members, setMembers] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [showInvite, setShowInvite] = useState(false)

  const toast = useCallback((message, severity = 'LOW', title = 'Success') => {
    addToast({ title, message, severity })
  }, [addToast])

  const tenantId = tenant?.id || ''

  const loadMembers = useCallback(async () => {
    if (!tenantId) {
      setMembers([])
      return
    }
    setLoading(true)
    try {
      const [membersData, usersData] = await Promise.all([
        fetchTenantMembers(tenantId),
        fetchUsers(),
      ])
      setMembers(Array.isArray(membersData) ? membersData : [])
      setUsers(Array.isArray(usersData) ? usersData : (usersData?.items || []))
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to load tenant members', 'CRITICAL', 'Error')
    } finally {
      setLoading(false)
    }
  }, [tenantId, toast])

  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  const userMap = useMemo(
    () => new Map(users.map((user) => [String(user.id), user])),
    [users]
  )

  const nonMembers = useMemo(
    () => users.filter((user) => !members.some((member) => String(member.user_id) === String(user.id))),
    [members, users]
  )

  const resolveUserLabel = useCallback((member) => {
    if (member.display_name) return member.display_name
    if (member.email) return member.email
    const user = userMap.get(String(member.user_id))
    return user?.display_name || user?.email || `${String(member.user_id).slice(0, 8)}…`
  }, [userMap])

  const resolveUserEmail = useCallback((member) => {
    if (member.email) return member.email
    const user = userMap.get(String(member.user_id))
    return user?.email || null
  }, [userMap])

  async function handleAdd(userId, role) {
    if (!tenantId || !userId) return
    try {
      const created = await addTenantMember(tenantId, { user_id: userId, role })
      setMembers((current) => [...current, created])
      toast('Tenant member added')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to add tenant member', 'CRITICAL', 'Error')
      throw err
    }
  }

  async function handleRoleChange(userId, role) {
    try {
      const updated = await updateTenantMember(tenantId, userId, { role })
      setMembers((current) => current.map((member) => (
        String(member.user_id) === String(userId)
          ? { ...member, role: updated.role }
          : member
      )))
      toast('Tenant role updated')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to update tenant member', 'CRITICAL', 'Error')
    }
  }

  async function handleRemove(userId) {
    try {
      await removeTenantMember(tenantId, userId)
      setMembers((current) => current.filter((member) => String(member.user_id) !== String(userId)))
      toast('Tenant member removed')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to remove tenant member', 'CRITICAL', 'Error')
    }
  }

  async function handleResendInvite(member) {
    if (!member.email) return
    try {
      await inviteTenantUser(tenantId, { email: member.email, role: member.role, display_name: member.display_name || '' })
      toast(`Invitation resent to ${member.email}`)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to resend invitation', 'CRITICAL', 'Error')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <Users size={14} />
            Members ({members.length})
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4, marginBottom: 0 }}>
            Manage access for {tenant?.display_name || tenant?.name || 'this workspace'}.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => setShowInvite(true)}
            aria-label="Invite Tenant User"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '7px 14px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
              background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.24)',
            }}
          >
            <Mail size={13} />
            Invite User
          </button>
          <button
            onClick={() => setShowAdd(true)}
            aria-label="Add Tenant Member"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '7px 14px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
              background: 'rgba(251,146,60,0.12)', color: 'var(--brand-orange)', border: '1px solid rgba(251,146,60,0.24)',
            }}
          >
            <Plus size={13} />
            Add Member
          </button>
        </div>
      </div>

      {/* Members list */}
      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px 0', fontSize: 13 }}>
          Loading members…
        </div>
      ) : members.length === 0 ? (
        <div style={{
          background: 'var(--bg-input)', border: '1px dashed var(--border)',
          borderRadius: 8, padding: '32px 16px', textAlign: 'center',
          fontSize: 13, color: 'var(--text-muted)',
        }}>
          No members yet. Add existing users or invite new ones.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {members.map((member) => {
            const label = resolveUserLabel(member)
            const email = resolveUserEmail(member)
            const isPending = member.is_active === false
            return (
              <div
                key={member.id || member.user_id}
                style={{
                  background: 'var(--bg-input)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '12px 14px',
                  display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
                }}
              >
                {/* Avatar */}
                <div style={{
                  width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
                  background: 'rgba(34,211,238,0.12)', border: '1px solid rgba(34,211,238,0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: 'var(--neon-cyan)',
                }}>
                  {label.charAt(0).toUpperCase()}
                </div>

                {/* Name / email */}
                <div style={{ flex: 1, minWidth: 140 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{label}</span>
                    {isPending && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
                        background: 'rgba(251,146,60,0.12)', color: 'var(--brand-orange)',
                        border: '1px solid rgba(251,146,60,0.24)', textTransform: 'uppercase', letterSpacing: '0.05em',
                      }}>
                        Pending
                      </span>
                    )}
                  </div>
                  {email && email !== label && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{email}</div>
                  )}
                </div>

                {/* Status badge */}
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                  whiteSpace: 'nowrap', flexShrink: 0,
                  ...(isPending
                    ? { background: 'rgba(251,146,60,0.12)', color: 'var(--brand-orange)', border: '1px solid rgba(251,146,60,0.24)' }
                    : { background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }
                  ),
                }}>
                  {isPending ? 'Pending' : 'Active'}
                </span>

                {/* Role selector — disabled for pending */}
                <select
                  aria-label={`Role for ${label}`}
                  value={member.role}
                  onChange={(e) => handleRoleChange(member.user_id, e.target.value)}
                  disabled={isPending}
                  style={{ ...inputCls, width: 'auto', minWidth: 110, padding: '6px 10px', opacity: isPending ? 0.5 : 1 }}
                >
                  {TENANT_ROLE_OPTIONS.map((role) => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>

                {/* Resend invite (pending only) */}
                {isPending && (
                  <button
                    onClick={() => handleResendInvite(member)}
                    title="Resend invitation email"
                    style={{
                      display: 'flex', alignItems: 'center', gap: 4,
                      padding: '5px 10px', borderRadius: 6, border: '1px solid rgba(34,211,238,0.25)',
                      background: 'rgba(34,211,238,0.08)', color: 'var(--neon-cyan)',
                      fontSize: 11, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
                    }}
                  >
                    <RefreshCw size={11} />
                    Resend
                  </button>
                )}

                {/* Remove */}
                <button
                  onClick={() => handleRemove(member.user_id)}
                  title="Remove member"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: 4, display: 'flex' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )
          })}
        </div>
      )}

      {showAdd && (
        <AddMemberModal
          nonMembers={nonMembers}
          onClose={() => setShowAdd(false)}
          onAdd={handleAdd}
        />
      )}

      {showInvite && (
        <InviteTenantUserModal
          tenant={tenant}
          onClose={() => setShowInvite(false)}
          onInvited={() => loadMembers()}
        />
      )}
    </div>
  )
}
