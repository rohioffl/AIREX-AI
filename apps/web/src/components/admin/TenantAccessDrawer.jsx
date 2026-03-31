import { useCallback, useEffect, useMemo, useState } from 'react'
import { Building2, ShieldCheck, UserRound, X } from 'lucide-react'

import { useAuth } from '../../context/AuthContext'
import { useToasts } from '../../context/ToastContext'
import {
  fetchUserAccessibleTenants,
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

function AccessPill({ active, label }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        padding: '3px 8px',
        borderRadius: 999,
        color: active ? 'var(--neon-green)' : 'var(--text-muted)',
        background: active ? 'rgba(52,211,153,0.12)' : 'rgba(148,163,184,0.08)',
        border: `1px solid ${active ? 'rgba(52,211,153,0.28)' : 'var(--border)'}`,
      }}
    >
      {label}
    </span>
  )
}

export default function TenantAccessDrawer({ user, tenants = [], open, onClose }) {
  const auth = useAuth()
  const { addToast } = useToasts()
  const [accessibleTenants, setAccessibleTenants] = useState([])
  const [loading, setLoading] = useState(false)
  const [draftRoles, setDraftRoles] = useState({})
  const [busyTenantId, setBusyTenantId] = useState(null)
  const currentUserId = auth?.user?.userId || auth?.user?.user_id || auth?.user?.id || null
  const isCurrentUser = String(user?.id) === String(currentUserId)

  const toast = useCallback((message, severity = 'LOW', title = 'Success') => {
    addToast({ title, message, severity })
  }, [addToast])

  const loadAccessibleTenants = useCallback(async () => {
    if (!user?.id) return
    setLoading(true)
    try {
      const data = await fetchUserAccessibleTenants(user.id)
      setAccessibleTenants(Array.isArray(data) ? data : [])
    } catch (err) {
      setAccessibleTenants([])
      toast(extractErrorMessage(err) || 'Failed to load workspace access', 'CRITICAL', 'Error')
    } finally {
      setLoading(false)
    }
  }, [toast, user?.id])

  useEffect(() => {
    if (!open || !user?.id) return
    let active = true
    async function load() {
      try {
        await loadAccessibleTenants()
      } catch (err) {
        if (active) {
          toast(extractErrorMessage(err) || 'Failed to load workspace access', 'CRITICAL', 'Error')
        }
      }
    }
    load()
    return () => {
      active = false
    }
  }, [loadAccessibleTenants, open, toast, user?.id])

  useEffect(() => {
    const nextDrafts = {}
    tenants.forEach((tenant) => {
      const access = accessibleTenants.find((row) => String(row.id) === String(tenant.id))
      nextDrafts[String(tenant.id)] = access?.membership_role || 'viewer'
    })
    setDraftRoles(nextDrafts)
  }, [accessibleTenants, tenants])

  const accessMap = useMemo(
    () => new Map(accessibleTenants.map((tenant) => [String(tenant.id), tenant])),
    [accessibleTenants]
  )
  const scopedAccessibleTenants = useMemo(
    () => accessibleTenants.filter((tenant) => tenants.some((scopedTenant) => String(scopedTenant.id) === String(tenant.id))),
    [accessibleTenants, tenants]
  )

  async function handleRoleChange(tenantId) {
    const role = draftRoles[String(tenantId)] || 'viewer'
    setBusyTenantId(String(tenantId))
    try {
      await updateTenantMember(tenantId, user.id, { role })
      await loadAccessibleTenants()
      toast('Explicit workspace role updated')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to update workspace access', 'CRITICAL', 'Error')
    } finally {
      setBusyTenantId(null)
    }
  }

  async function handleRemove(tenantId) {
    setBusyTenantId(String(tenantId))
    try {
      await removeTenantMember(tenantId, user.id)
      await loadAccessibleTenants()
      toast('Explicit workspace access removed')
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to remove workspace access', 'CRITICAL', 'Error')
    } finally {
      setBusyTenantId(null)
    }
  }

  if (!open) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }} onClick={onClose} />
      <div className="glass flex flex-col" style={{ position: 'relative', width: 480, maxWidth: '100vw', height: '100vh', borderLeft: '1px solid var(--border)' }}>
        <div className="flex items-start justify-between gap-4" style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)' }}>
          <div>
            <div className="flex items-center gap-2">
              <UserRound size={16} style={{ color: 'var(--neon-cyan)' }} />
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)' }}>Workspace Access</div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
              {user?.display_name || user?.email || String(user?.id || '').slice(0, 8)}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }} className="space-y-4">
          <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2" style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <ShieldCheck size={14} />
              Access Summary
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8 }}>
              {scopedAccessibleTenants.length} workspace{scopedAccessibleTenants.length === 1 ? '' : 's'} currently visible to this user in this organization.
            </div>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px 0' }}>Loading workspace access…</div>
          ) : tenants.length === 0 ? (
            <div className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
              No workspaces are attached to this organization yet.
            </div>
          ) : (
            tenants.map((tenant) => {
              const access = accessMap.get(String(tenant.id))
              return (
                <div key={tenant.id} className="rounded-xl p-4 space-y-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{tenant.display_name || tenant.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                        {tenant.name}
                      </div>
                    </div>
                    <AccessPill active={!!access} label={access ? 'Accessible' : 'No direct access'} />
                  </div>
                  <div className="flex items-center gap-2 text-xs flex-wrap" style={{ color: 'var(--text-secondary)' }}>
                    <Building2 size={13} />
                    <span>{tenant.cloud?.toUpperCase?.() || 'Unknown cloud'}</span>
                    {access?.membership_role && <AccessPill active label={`Explicit ${access.membership_role}`} />}
                    {!access?.membership_role && access && <AccessPill active label="Inherited or home workspace" />}
                  </div>

                  {access?.membership_role ? (
                    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-2 items-center">
                      <select
                        aria-label={`Workspace access role for ${tenant.display_name || tenant.name}`}
                        value={draftRoles[String(tenant.id)] || 'viewer'}
                        onChange={(e) => setDraftRoles((current) => ({ ...current, [String(tenant.id)]: e.target.value }))}
                        disabled={isCurrentUser}
                        style={inputCls}
                      >
                        {TENANT_ROLE_OPTIONS.map((role) => (
                          <option key={role.value} value={role.value}>{role.label}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => handleRoleChange(tenant.id)}
                        disabled={isCurrentUser || busyTenantId === String(tenant.id)}
                        className="px-3 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                        style={{ background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.22)', color: 'var(--neon-cyan)' }}
                      >
                        Save Role
                      </button>
                      <button
                        onClick={() => handleRemove(tenant.id)}
                        disabled={isCurrentUser || busyTenantId === String(tenant.id)}
                        className="px-3 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                        style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444' }}
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div
                      className="rounded-lg p-3"
                      style={{ background: 'rgba(148,163,184,0.08)', border: '1px dashed var(--border)', color: 'var(--text-secondary)', fontSize: 12 }}
                    >
                      New explicit workspace access is invite-only. Use the workspace members panel to send an invitation instead of assigning access here.
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
