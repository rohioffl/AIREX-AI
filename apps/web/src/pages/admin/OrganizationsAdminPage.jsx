import { useMemo, useState } from 'react'
import { Building2, Globe, Layers } from 'lucide-react'
import { Link } from 'react-router-dom'

import AccessMatrixView from '../../components/admin/AccessMatrixView'
import TenantAccessDrawer from '../../components/admin/TenantAccessDrawer'
import TenantWorkspaceManager from '../../components/admin/TenantWorkspaceManager'
import { useAuth } from '../../context/AuthContext'
import { isPlatformAdmin } from '../../utils/accessControl'

function SummaryCard({ label, value, icon: Icon, color }) {
  return (
    <div className="glass rounded-xl p-4" style={{ border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between">
        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        <Icon size={14} style={{ color, opacity: 0.75 }} />
      </div>
      <div style={{ marginTop: 10, fontSize: 24, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</div>
    </div>
  )
}

export default function OrganizationsAdminPage() {
  const auth = useAuth()
  const {
    organizations = [],
    tenants = [],
    organizationMemberships = [],
    activeOrganization = null,
  } = auth
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(activeOrganization?.id || organizations[0]?.id || '')
  const [inspectedUser, setInspectedUser] = useState(null)
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/dashboard'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Dashboard'
  const selectedOrganization = useMemo(
    () => organizations.find((org) => org.id === selectedOrganizationId) || activeOrganization || organizations[0] || null,
    [activeOrganization, organizations, selectedOrganizationId]
  )
  const organizationTenants = useMemo(
    () => tenants.filter((tenant) => tenant.organization_id === selectedOrganization?.id),
    [selectedOrganization?.id, tenants]
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            Organization Admin
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Finalize organization setup, onboard tenant workspaces, and keep scoped admin access aligned with customer boundaries.
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard label="Organizations" value={organizations.length} icon={Globe} color="#22d3ee" />
        <SummaryCard label="Tenant Spaces" value={tenants.length} icon={Layers} color="var(--brand-orange)" />
        <SummaryCard label="Scoped Memberships" value={organizationMemberships.length} icon={Building2} color="var(--neon-indigo)" />
      </div>

      <div className="glass rounded-xl p-5 space-y-2" style={{ border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Workspace Onboarding
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Use the workspace manager below to create organizations, attach tenants, and verify tenant placement before integrations and memberships are configured.
        </p>
      </div>

      <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Organization Scope
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Select an organization to review org roles and inspect inherited tenant access.
          </p>
        </div>
        <div style={{ maxWidth: 360 }}>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Organization</label>
          <select
            aria-label="Organization scope"
            value={selectedOrganization?.id || ''}
            onChange={(e) => setSelectedOrganizationId(e.target.value)}
            className="w-full rounded-lg px-3 py-2"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
          >
            {(organizations.length ? organizations : activeOrganization ? [activeOrganization] : []).map((org) => (
              <option key={org.id} value={org.id}>{org.name}</option>
            ))}
          </select>
        </div>
      </div>

      {selectedOrganization && (
        <AccessMatrixView
          organization={selectedOrganization}
          tenants={organizationTenants}
          onInspectUser={setInspectedUser}
        />
      )}

      <TenantWorkspaceManager mode="organizations" />

      <TenantAccessDrawer
        open={!!inspectedUser}
        user={inspectedUser}
        tenants={organizationTenants}
        onClose={() => setInspectedUser(null)}
      />
    </div>
  )
}
