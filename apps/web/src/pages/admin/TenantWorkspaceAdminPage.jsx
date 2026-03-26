import { useAuth } from '../../context/AuthContext'
import { isPlatformAdmin } from '../../utils/accessControl'
import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'

import TenantMembersPanel from '../../components/admin/TenantMembersPanel'
import TenantWorkspaceManager from '../../components/admin/TenantWorkspaceManager'

export default function TenantWorkspaceAdminPage() {
  const auth = useAuth()
  const { tenants = [], activeTenant = null } = auth
  const [selectedTenantId, setSelectedTenantId] = useState(activeTenant?.id || tenants[0]?.id || '')
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/admin/organizations'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Organizations'
  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === selectedTenantId) || activeTenant || tenants[0] || null,
    [activeTenant, selectedTenantId, tenants]
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            Tenant Workspaces
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Manage tenants, project structure, and workspace-level operational details.
          </p>
        </div>
        <Link
          to={backTarget}
          className="px-4 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          {backLabel}
        </Link>
      </div>

      <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Tenant Access Control
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Select a tenant workspace to manage explicit member access alongside the workspace inventory below.
          </p>
        </div>
        <div style={{ maxWidth: 360 }}>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Tenant Workspace</label>
          <select
            aria-label="Tenant workspace scope"
            value={selectedTenant?.id || ''}
            onChange={(e) => setSelectedTenantId(e.target.value)}
            className="w-full rounded-lg px-3 py-2"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          >
            {(tenants.length ? tenants : activeTenant ? [activeTenant] : []).map((tenant) => (
              <option key={tenant.id} value={tenant.id}>{tenant.display_name || tenant.name}</option>
            ))}
          </select>
        </div>
      </div>

      {selectedTenant && <TenantMembersPanel tenant={selectedTenant} />}

      <TenantWorkspaceManager mode="workspace" />
    </div>
  )
}
