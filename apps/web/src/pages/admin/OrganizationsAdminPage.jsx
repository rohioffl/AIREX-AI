import { Link } from 'react-router-dom'

import TenantWorkspaceManager from '../../components/admin/TenantWorkspaceManager'

export default function OrganizationsAdminPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            Organization Admin
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Create organizations and onboard tenants into the right customer workspace.
          </p>
        </div>
        <Link
          to="/admin"
          className="px-4 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          Back to Admin
        </Link>
      </div>
      <TenantWorkspaceManager mode="organizations" />
    </div>
  )
}
