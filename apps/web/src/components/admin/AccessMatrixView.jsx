import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Shield, Trash2, UserCog } from 'lucide-react'

import { useToasts } from '../../context/ToastContext'
import {
  addOrgMember,
  fetchOrgMembers,
  fetchUserAccessibleTenants,
  fetchUsers,
  removeOrgMember,
  updateOrgMember,
} from '../../services/api'
import { extractErrorMessage } from '../../utils/errorHandler'

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

function roleCellColor(access) {
  if (access?.membership_role) return 'var(--brand-orange)'
  if (access) return 'var(--neon-green)'
  return 'var(--text-muted)'
}

function roleCellLabel(access) {
  if (access?.membership_role) return access.membership_role
  if (access) return 'inherited'
  return 'none'
}

export default function AccessMatrixView({ organization, tenants = [], onInspectUser }) {
  const { addToast } = useToasts()
  const [members, setMembers] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [addUserId, setAddUserId] = useState('')
  const [addRole, setAddRole] = useState('operator')
  const [saving, setSaving] = useState(false)
  const [tenantAccessByUserId, setTenantAccessByUserId] = useState({})

  const toast = useCallback((message, severity = 'LOW', title = 'Success') => {
    addToast({ title, message, severity })
  }, [addToast])

  const organizationId = organization?.id || ''

  const loadMembers = useCallback(async () => {
    if (!organizationId) {
      setMembers([])
      return
    }
    setLoading(true)
    try {
      const [membersData, usersData] = await Promise.all([
        fetchOrgMembers(organizationId),
        fetchUsers(),
      ])
      const nextMembers = Array.isArray(membersData) ? membersData : []
      setMembers(nextMembers)
      setUsers(Array.isArray(usersData) ? usersData : (usersData?.items || []))
      const tenantAccessRows = await Promise.all(
        nextMembers.map(async (member) => ({
          userId: String(member.user_id),
          rows: await fetchUserAccessibleTenants(member.user_id),
        }))
      )
      const nextAccessMap = {}
      tenantAccessRows.forEach(({ userId, rows }) => {
        nextAccessMap[userId] = Array.isArray(rows)
          ? rows.filter((row) => String(row.organization_id) === String(organizationId))
          : []
      })
      setTenantAccessByUserId(nextAccessMap)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to load organization access', 'CRITICAL', 'Error')
    } finally {
      setLoading(false)
    }
  }, [organizationId, toast])

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

  const resolveUserLabel = useCallback((userId) => {
    const user = userMap.get(String(userId))
    return user?.display_name || user?.email || `${String(userId).slice(0, 8)}…`
  }, [userMap])

  async function handleAdd() {
    if (!organizationId || !addUserId) return
    setSaving(true)
    try {
      const created = await addOrgMember(organizationId, { user_id: addUserId, role: addRole })
      setMembers((current) => [...current, created])
      setTenantAccessByUserId((current) => ({ ...current, [String(created.user_id)]: [] }))
      setAddUserId('')
      setAddRole('operator')
      setShowAdd(false)
      toast('Organization member added')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to add organization member', 'CRITICAL', 'Error')
    } finally {
      setSaving(false)
    }
  }

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
      setTenantAccessByUserId((current) => {
        const next = { ...current }
        delete next[String(userId)]
        return next
      })
      toast('Organization member removed')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to remove organization member', 'CRITICAL', 'Error')
    }
  }

  return (
    <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Access Matrix
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Review organization-level roles and open tenant access details for any member in {organization?.name || 'this organization'}.
          </p>
        </div>
        <button
          onClick={() => setShowAdd((current) => !current)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--neon-indigo)', border: '1px solid rgba(99,102,241,0.24)' }}
        >
          <Plus size={14} />
          Add Org Member
        </button>
      </div>

      {showAdd && (
        <div className="grid grid-cols-1 md:grid-cols-[1.5fr_0.9fr_auto] gap-3 items-end rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>User</label>
            <select aria-label="Organization member user" value={addUserId} onChange={(e) => setAddUserId(e.target.value)} style={inputCls}>
              <option value="">Select a user…</option>
              {nonMembers.map((user) => (
                <option key={user.id} value={user.id}>{user.display_name || user.email}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Role</label>
            <select aria-label="Organization member role" value={addRole} onChange={(e) => setAddRole(e.target.value)} style={inputCls}>
              {ORG_ROLE_OPTIONS.map((role) => (
                <option key={role.value} value={role.value}>{role.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleAdd}
            disabled={!addUserId || saving}
            className="px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
            style={{ background: 'var(--gradient-primary)', color: '#fff' }}
          >
            {saving ? 'Adding…' : 'Add'}
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '16px 0' }}>Loading organization access…</div>
      ) : members.length === 0 ? (
        <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
          No organization members found.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
          <table style={{ width: '100%', minWidth: 720, borderCollapse: 'separate', borderSpacing: 0 }}>
            <thead style={{ background: 'var(--bg-elevated)' }}>
              <tr>
                <th style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>User</th>
                <th style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>Org Role</th>
                {tenants.map((tenant) => (
                  <th key={tenant.id} style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>
                    <div>{tenant.display_name || tenant.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 500, marginTop: 4 }}>{tenant.cloud?.toUpperCase?.() || 'N/A'}</div>
                  </th>
                ))}
                <th style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => {
                const userAccessMap = new Map(
                  (tenantAccessByUserId[String(member.user_id)] || []).map((row) => [String(row.id), row])
                )
                return (
                  <tr key={member.id || member.user_id} style={{ background: 'var(--bg-input)' }}>
                    <td style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0" style={{ background: 'rgba(34,211,238,0.12)', color: 'var(--neon-cyan)', fontWeight: 700 }}>
                          {initials(resolveUserLabel(member.user_id))}
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{resolveUserLabel(member.user_id)}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                            {String(member.user_id)}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-2 min-w-[180px]">
                        <Shield size={14} style={{ color: 'var(--text-muted)' }} />
                        <select
                          aria-label={`Organization role for ${resolveUserLabel(member.user_id)}`}
                          value={member.role}
                          onChange={(e) => handleRoleChange(member.user_id, e.target.value)}
                          style={{ ...inputCls, padding: '6px 10px' }}
                        >
                          {ORG_ROLE_OPTIONS.map((role) => (
                            <option key={role.value} value={role.value}>{role.label}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                    {tenants.map((tenant) => {
                      const access = userAccessMap.get(String(tenant.id))
                      return (
                        <td key={`${member.user_id}-${tenant.id}`} style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                          <div
                            aria-label={`Access cell ${resolveUserLabel(member.user_id)} ${tenant.display_name || tenant.name}`}
                            className="inline-flex items-center gap-2 rounded-lg px-3 py-2"
                            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: roleCellColor(access), fontSize: 12, fontWeight: 700, textTransform: 'capitalize' }}
                          >
                            <span>{roleCellLabel(access)}</span>
                          </div>
                        </td>
                      )
                    })}
                    <td style={{ padding: '14px', borderBottom: '1px solid var(--border)' }}>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => onInspectUser?.(userMap.get(String(member.user_id)) || { id: member.user_id, display_name: resolveUserLabel(member.user_id) })}
                          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold"
                          style={{ background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.2)', color: 'var(--neon-cyan)' }}
                        >
                          <UserCog size={14} />
                          View
                        </button>
                        <button
                          onClick={() => handleRemove(member.user_id)}
                          title="Remove organization member"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: 6 }}
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
