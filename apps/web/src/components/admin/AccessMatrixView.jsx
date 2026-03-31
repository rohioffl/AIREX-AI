import { useCallback, useEffect, useState } from 'react'
import { Mail, RefreshCw, Shield, Trash2, UserCog } from 'lucide-react'

import { useToasts } from '../../context/ToastContext'
import { useAuth } from '../../context/AuthContext'
import {
  fetchOrgMembers,
  removeOrgMember,
  resendOrgInvitation,
  updateOrgMember,
} from '../../services/api'
import { extractErrorMessage } from '../../utils/errorHandler'
import InviteOrgMemberModal from './InviteOrgMemberModal'

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

const ORG_ROLE_OPTIONS = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'operator', label: 'Operator' },
  { value: 'admin', label: 'Admin' },
]

function initials(label) {
  return (label || '?').trim().charAt(0).toUpperCase()
}

function memberStatusMeta(member) {
  if (member?.invitation_status === 'expired') {
    return {
      label: 'Expired',
      color: '#f87171',
      background: 'rgba(248,113,113,0.1)',
      border: '1px solid rgba(248,113,113,0.24)',
    }
  }
  if (member?.invitation_status === 'pending' || member?.is_active === false) {
    return {
      label: 'Pending',
      color: '#f59e0b',
      background: 'rgba(245,158,11,0.1)',
      border: '1px solid rgba(245,158,11,0.24)',
    }
  }
  return {
    label: 'Active',
    color: '#22c55e',
    background: 'rgba(34,197,94,0.1)',
    border: '1px solid rgba(34,197,94,0.24)',
  }
}

export default function AccessMatrixView({ organization, tenants = [], onInspectUser }) {
  const auth = useAuth()
  const { addToast } = useToasts()
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(false)
  const [showInvite, setShowInvite] = useState(false)

  const toast = useCallback((message, severity = 'LOW', title = 'Success') => {
    addToast({ title, message, severity })
  }, [addToast])

  const organizationId = organization?.id || ''
  const currentUserId = auth?.user?.userId || auth?.user?.user_id || auth?.user?.id || null

  const loadMembers = useCallback(async () => {
    if (!organizationId) {
      setMembers([])
      return
    }
    setLoading(true)
    try {
      const membersData = await fetchOrgMembers(organizationId)
      const nextMembers = Array.isArray(membersData) ? membersData : []
      setMembers(nextMembers)
    } catch (err) {
      setMembers([])
      toast(extractErrorMessage(err) || 'Failed to load organization access', 'CRITICAL', 'Error')
    } finally {
      setLoading(false)
    }
  }, [organizationId, toast])

  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  const resolveUserLabel = useCallback((member) => {
    return member?.display_name || member?.email || `${String(member?.user_id).slice(0, 8)}…`
  }, [])

  async function handleRoleChange(userId, role) {
    try {
      const updated = await updateOrgMember(organizationId, userId, { role })
      setMembers((current) => current.map((member) => (
        String(member.user_id) === String(userId)
          ? { ...member, role: updated.role }
          : member
      )))
      toast('Organization role updated')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to update organization member', 'CRITICAL', 'Error')
    }
  }

  async function handleRemove(userId) {
    try {
      await removeOrgMember(organizationId, userId)
      setMembers((current) => current.filter((member) => String(member.user_id) !== String(userId)))
      toast('Organization member removed')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to remove organization member', 'CRITICAL', 'Error')
    }
  }

  async function handleResendInvite(member) {
    try {
      const data = await resendOrgInvitation(organizationId, member.user_id)
      const message = data.delivery_mode === 'accept_invitation'
        ? `Accept invitation email resent to ${data.email}`
        : `Invitation resent to ${data.email}`
      toast(message)
      loadMembers()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to resend invitation', 'CRITICAL', 'Error')
    }
  }

  return (
    <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Organization Members
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Review organization-level roles for members in {organization?.name || 'this organization'}. New access is invite-only.
          </p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.24)' }}
        >
          <Mail size={14} />
          Invite Org Member
        </button>
      </div>

      {showInvite && (
        <InviteOrgMemberModal
          organization={organization}
          tenants={tenants}
          onClose={() => setShowInvite(false)}
          onInvited={() => {
            setShowInvite(false)
            loadMembers()
          }}
        />
      )}

      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '16px 0' }}>Loading organization access…</div>
      ) : members.length === 0 ? (
        <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
          No organization members found.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
          <table style={{ width: '100%', minWidth: 520, borderCollapse: 'separate', borderSpacing: 0 }}>
            <thead style={{ background: 'var(--bg-elevated)' }}>
              <tr>
                <th style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>User</th>
                <th style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>Org Role</th>
                <th style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => {
                const statusMeta = memberStatusMeta(member)
                const isCurrentUser = String(member.user_id) === String(currentUserId)
                return (
                  <tr key={member.id || member.user_id} style={{ background: 'var(--bg-input)' }}>
                    <td style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0" style={{ background: 'rgba(34,211,238,0.12)', color: 'var(--neon-cyan)', fontWeight: 700 }}>
                          {initials(resolveUserLabel(member))}
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{resolveUserLabel(member)}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                            {member.email || String(member.user_id)}
                          </div>
                          <div style={{ marginTop: 8 }}>
                            <span
                              aria-label={`Organization member status for ${resolveUserLabel(member)}`}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                                fontSize: 10,
                                fontWeight: 700,
                                padding: '3px 8px',
                                borderRadius: 999,
                                color: statusMeta.color,
                                background: statusMeta.background,
                                border: statusMeta.border,
                                letterSpacing: '0.03em',
                                textTransform: 'uppercase',
                              }}
                            >
                              {statusMeta.label}
                            </span>
                            {isCurrentUser && (
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  marginLeft: 8,
                                  fontSize: 10,
                                  fontWeight: 700,
                                  padding: '3px 8px',
                                  borderRadius: 999,
                                  color: 'var(--neon-cyan)',
                                  background: 'rgba(34,211,238,0.08)',
                                  border: '1px solid rgba(34,211,238,0.22)',
                                  letterSpacing: '0.03em',
                                  textTransform: 'uppercase',
                                }}
                              >
                                You
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-2 min-w-[180px]">
                        <Shield size={14} style={{ color: 'var(--text-muted)' }} />
                        <select
                          aria-label={`Organization role for ${resolveUserLabel(member)}`}
                          value={member.role}
                          onChange={(e) => handleRoleChange(member.user_id, e.target.value)}
                          disabled={isCurrentUser}
                          style={{ ...inputCls, padding: '6px 10px' }}
                        >
                          {ORG_ROLE_OPTIONS.map((role) => (
                            <option key={role.value} value={role.value}>{role.label}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    <td style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => onInspectUser?.({
                            id: member.user_id,
                            display_name: resolveUserLabel(member),
                            email: member.email,
                            is_active: member.is_active,
                            invitation_status: member.invitation_status,
                          })}
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold"
                          style={{ background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.2)', color: 'var(--neon-cyan)' }}
                        >
                          <UserCog size={14} />
                          View
                        </button>
                        {member.invitation_status === 'pending' && (
                          <button
                            onClick={() => handleResendInvite(member)}
                            title="Resend invitation email"
                            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold"
                            style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.22)', color: 'var(--neon-cyan)' }}
                          >
                            <RefreshCw size={14} />
                            Resend
                          </button>
                        )}
                        <button
                          onClick={() => handleRemove(member.user_id)}
                          title="Remove organization member"
                          disabled={isCurrentUser}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: isCurrentUser ? 'not-allowed' : 'pointer',
                            color: isCurrentUser ? 'var(--text-muted)' : '#ef4444',
                            padding: 6,
                            opacity: isCurrentUser ? 0.45 : 1,
                          }}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
