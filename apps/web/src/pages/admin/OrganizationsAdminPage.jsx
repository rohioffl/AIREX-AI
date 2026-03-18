import { Building2, Globe, Layers } from 'lucide-react'
import { Link } from 'react-router-dom'

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
  const { organizations = [], tenants = [], organizationMemberships = [] } = auth
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/dashboard'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Dashboard'

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

      <TenantWorkspaceManager mode="organizations" />
    </div>
  )
}
