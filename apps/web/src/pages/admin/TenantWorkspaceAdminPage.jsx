import { useAuth } from '../../context/AuthContext'
import { isPlatformAdmin } from '../../utils/accessControl'
import { Link } from 'react-router-dom'

import TenantWorkspaceManager from '../../components/admin/TenantWorkspaceManager'

export default function TenantWorkspaceAdminPage() {
  const auth = useAuth()
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/admin/organizations'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Organizations'

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
      <TenantWorkspaceManager mode="workspace" />
    </div>
  )
}
