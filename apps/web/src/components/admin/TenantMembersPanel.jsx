import { useCallback, useEffect, useState } from 'react'
import { Mail, RefreshCw, Trash2, Users } from 'lucide-react'

import { useAuth } from '../../context/AuthContext'
import { useToasts } from '../../context/ToastContext'
import {
  fetchTenantMembers,
  removeTenantMember,
  resendTenantInvitation,
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

export default function TenantMembersPanel({ tenant }) {
  const auth = useAuth()
  const { addToast } = useToasts()
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [showInvite, setShowInvite] = useState(false)

  const toast = useCallback((message, severity = 'LOW', title = 'Success') => {
    addToast({ title, message, severity })
  }, [addToast])

  const tenantId = tenant?.id || ''
  const currentUserId = auth?.user?.userId || auth?.user?.user_id || auth?.user?.id || null

  const loadMembers = useCallback(async () => {
    if (!tenantId) {
      setMembers([])
      return
    }
    setLoading(true)
    try {
      const membersData = await fetchTenantMembers(tenantId)
      setMembers(Array.isArray(membersData) ? membersData : [])
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to load workspace members', 'CRITICAL', 'Error')
    } finally {
      setLoading(false)
    }
  }, [tenantId, toast])

  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  const resolveUserLabel = useCallback((member) => {
    if (member.display_name) return member.display_name
    if (member.email) return member.email
    return `${String(member.user_id).slice(0, 8)}…`
  }, [])

  const resolveUserEmail = useCallback((member) => {
    if (member.email) return member.email
    return null
  }, [])

  async function handleRoleChange(userId, role) {
    try {
      const updated = await updateTenantMember(tenantId, userId, { role })
      setMembers((current) => current.map((member) => (
        String(member.user_id) === String(userId)
          ? { ...member, role: updated.role }
          : member
      )))
      toast('Workspace role updated')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to update workspace member', 'CRITICAL', 'Error')
    }
  }

  async function handleRemove(userId) {
    try {
      await removeTenantMember(tenantId, userId)
      setMembers((current) => current.filter((member) => String(member.user_id) !== String(userId)))
      toast('Workspace member removed')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to remove workspace member', 'CRITICAL', 'Error')
    }
  }

  async function handleResendInvite(member) {
    if (!member.email) return
    try {
      await resendTenantInvitation(tenantId, member.user_id)
      toast(`Invitation resent to ${member.email}`)
      loadMembers()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to resend invitation', 'CRITICAL', 'Error')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <Users size={14} />
            Members ({members.length})
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4, marginBottom: 0 }}>
            Manage access for {tenant?.display_name || tenant?.name || 'this workspace'}. New members are invite-only.
          </p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          aria-label="Invite Workspace User"
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer',
            background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.24)',
          }}
        >
          <Mail size={13} />
          Invite User
        </button>
      </div>

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
          No members yet. Invite a user to grant workspace access.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {members.map((member) => {
            const label = resolveUserLabel(member)
            const email = resolveUserEmail(member)
            const isPending = member.is_active === false
            const isCurrentUser = String(member.user_id) === String(currentUserId)
            return (
              <div
                key={member.id || member.user_id}
                style={{
                  background: 'var(--bg-input)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '12px 14px',
                  display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
                }}
              >
                <div style={{
                  width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
                  background: 'rgba(34,211,238,0.12)', border: '1px solid rgba(34,211,238,0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: 'var(--neon-cyan)',
                }}>
                  {label.charAt(0).toUpperCase()}
                </div>

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
                    {isCurrentUser && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4,
                        background: 'rgba(34,211,238,0.08)', color: 'var(--neon-cyan)',
                        border: '1px solid rgba(34,211,238,0.22)', textTransform: 'uppercase', letterSpacing: '0.05em',
                      }}>
                        You
                      </span>
                    )}
                  </div>
                  {email && email !== label && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{email}</div>
                  )}
                </div>

                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                  whiteSpace: 'nowrap', flexShrink: 0,
                  ...(isPending
                    ? { background: 'rgba(251,146,60,0.12)', color: 'var(--brand-orange)', border: '1px solid rgba(251,146,60,0.24)' }
                    : { background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }),
                }}>
                  {isPending ? 'Pending' : 'Active'}
                </span>

                <select
                  aria-label={`Role for ${label}`}
                  value={member.role}
                  onChange={(e) => handleRoleChange(member.user_id, e.target.value)}
                  style={{ ...inputCls, width: 'auto', minWidth: 110, padding: '6px 10px', opacity: (isPending || isCurrentUser) ? 0.5 : 1 }}
                  disabled={isPending || isCurrentUser}
                >
                  {TENANT_ROLE_OPTIONS.map((role) => (
                    <option key={role.value} value={role.value}>{role.label}</option>
                  ))}
                </select>

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

                <button
                  onClick={() => handleRemove(member.user_id)}
                  title="Remove member"
                  disabled={isCurrentUser}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: isCurrentUser ? 'not-allowed' : 'pointer',
                    color: isCurrentUser ? 'var(--text-muted)' : '#ef4444',
                    padding: 4,
                    display: 'flex',
                    opacity: isCurrentUser ? 0.45 : 1,
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )
          })}
        </div>
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
