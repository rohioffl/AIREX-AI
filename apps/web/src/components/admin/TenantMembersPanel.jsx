import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, Users } from 'lucide-react'

import { useToasts } from '../../context/ToastContext'
import {
  addTenantMember,
  fetchTenantMembers,
  fetchUsers,
  removeTenantMember,
  updateTenantMember,
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

const TENANT_ROLE_OPTIONS = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'operator', label: 'Operator' },
  { value: 'admin', label: 'Admin' },
]

export default function TenantMembersPanel({ tenant }) {
  const { addToast } = useToasts()
  const [members, setMembers] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [addUserId, setAddUserId] = useState('')
  const [addRole, setAddRole] = useState('viewer')
  const [saving, setSaving] = useState(false)

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

  const resolveUserLabel = useCallback((userId) => {
    const user = userMap.get(String(userId))
    return user?.display_name || user?.email || `${String(userId).slice(0, 8)}…`
  }, [userMap])

  async function handleAdd() {
    if (!tenantId || !addUserId) return
    setSaving(true)
    try {
      const created = await addTenantMember(tenantId, { user_id: addUserId, role: addRole })
      setMembers((current) => [...current, created])
      setAddUserId('')
      setAddRole('viewer')
      setShowAdd(false)
      toast('Tenant member added')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to add tenant member', 'CRITICAL', 'Error')
    } finally {
      setSaving(false)
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

  return (
    <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2" style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <Users size={14} />
            Tenant Members
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Manage explicit access for {tenant?.display_name || tenant?.name || 'the selected tenant'}.
          </p>
        </div>
        <button
          onClick={() => setShowAdd((current) => !current)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--brand-orange)', border: '1px solid rgba(251,146,60,0.24)' }}
        >
          <Plus size={14} />
          Add Tenant Member
        </button>
      </div>

      {showAdd && (
        <div className="grid grid-cols-1 md:grid-cols-[1.5fr_0.9fr_auto] gap-3 items-end rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>User</label>
            <select aria-label="Tenant member user" value={addUserId} onChange={(e) => setAddUserId(e.target.value)} style={inputCls}>
              <option value="">Select a user…</option>
              {nonMembers.map((user) => (
                <option key={user.id} value={user.id}>{user.display_name || user.email}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Role</label>
            <select aria-label="Tenant member role" value={addRole} onChange={(e) => setAddRole(e.target.value)} style={inputCls}>
              {TENANT_ROLE_OPTIONS.map((role) => (
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
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '16px 0' }}>Loading tenant members…</div>
      ) : members.length === 0 ? (
        <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
          No explicit tenant members configured yet.
        </div>
      ) : (
        <div className="space-y-3">
          {members.map((member) => (
            <div key={member.id || member.user_id} className="rounded-xl p-4 flex items-center gap-3 flex-wrap" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div className="flex-1 min-w-[180px]">
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{resolveUserLabel(member.user_id)}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                  {String(member.user_id)}
                </div>
              </div>
              <select
                aria-label={`Tenant role for ${resolveUserLabel(member.user_id)}`}
                value={member.role}
                onChange={(e) => handleRoleChange(member.user_id, e.target.value)}
                style={{ ...inputCls, minWidth: 180 }}
              >
                {TENANT_ROLE_OPTIONS.map((role) => (
                  <option key={role.value} value={role.value}>{role.label}</option>
                ))}
              </select>
              <button
                onClick={() => handleRemove(member.user_id)}
                title="Remove tenant member"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: 6 }}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
