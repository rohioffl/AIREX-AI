import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCcw } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import AccessMatrixView from '../../components/admin/AccessMatrixView'
import TenantAccessDrawer from '../../components/admin/TenantAccessDrawer'
import TenantWorkspaceManager from '../../components/admin/TenantWorkspaceManager'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizationTenants, fetchOrganizations } from '../../services/api'
import { setActiveOrganizationIdOverride } from '../../utils/organizationScope'
import { isPlatformAdmin } from '../../utils/accessControl'

export default function OrganizationsAdminPage() {
  const { organizationSlug = '' } = useParams()
  const auth = useAuth()
  const {
    organizations: authOrganizations = [],
    activeOrganization = null,
  } = auth
  const [inspectedUser, setInspectedUser] = useState(null)
  const [remoteOrganizations, setRemoteOrganizations] = useState([])
  const [organizationTenants, setOrganizationTenants] = useState([])
  const [organizationsLoading, setOrganizationsLoading] = useState(true)
  const [tenantsLoading, setTenantsLoading] = useState(false)
  const [pageError, setPageError] = useState('')
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/dashboard'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Dashboard'
  const organizations = useMemo(
    () => (remoteOrganizations.length ? remoteOrganizations : authOrganizations),
    [authOrganizations, remoteOrganizations]
  )

  const loadOrganizations = useCallback(async () => {
    setOrganizationsLoading(true)
    setPageError('')
    try {
      const data = await fetchOrganizations()
      setRemoteOrganizations(Array.isArray(data) ? data : [])
    } catch {
      setRemoteOrganizations([])
      setPageError('Failed to load organizations.')
    } finally {
      setOrganizationsLoading(false)
    }
  }, [])

  const selectedOrganization = useMemo(() => {
    if (!organizationSlug) {
      return activeOrganization || organizations[0] || null
    }
    return organizations.find((org) => (
      String(org.slug) === String(organizationSlug) || String(org.id) === String(organizationSlug)
    )) || null
  }, [activeOrganization, organizationSlug, organizations])

  const visibleTenants = organizationTenants

  const loadOrganizationTenants = useCallback(async (organizationId) => {
    if (!organizationId) {
      setOrganizationTenants([])
      return
    }
    setTenantsLoading(true)
    setPageError('')
    try {
      const data = await fetchOrganizationTenants(organizationId)
      setOrganizationTenants(Array.isArray(data) ? data : [])
    } catch {
      setOrganizationTenants([])
      setPageError('Failed to load organization workspaces.')
    } finally {
      setTenantsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedOrganization?.id) {
      setActiveOrganizationIdOverride(String(selectedOrganization.id))
    }
  }, [selectedOrganization?.id])

  useEffect(() => {
    loadOrganizations()
  }, [loadOrganizations])

  useEffect(() => {
    if (!selectedOrganization?.id) return
    setActiveOrganizationIdOverride(String(selectedOrganization.id))
  }, [selectedOrganization?.id])

  useEffect(() => {
    if (selectedOrganization?.id) {
      loadOrganizationTenants(selectedOrganization.id)
    }
  }, [loadOrganizationTenants, selectedOrganization?.id])

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            Organization Admin
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            {selectedOrganization
              ? `Manage ${selectedOrganization.name} members and keep its workspace access aligned to that organization only.`
              : 'Manage one organization at a time with org-scoped members and workspaces.'}
          </p>
        </div>
        <Link
          to={backTarget}
          className="px-4 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          {backLabel}
        </Link>
        <button
          onClick={() => {
            loadOrganizations()
            if (selectedOrganization?.id) {
              loadOrganizationTenants(selectedOrganization.id)
            }
          }}
          className="px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-2"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          <RefreshCcw size={14} />
          Refresh
        </button>
      </div>

      {pageError && (
        <div className="glass rounded-xl p-4" style={{ border: '1px solid var(--border)', color: '#f87171' }}>
          {pageError}
        </div>
      )}

      {organizationsLoading ? (
        <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
          Loading organizations…
        </div>
      ) : null}

      {!organizationsLoading && selectedOrganization && (
        <AccessMatrixView
          organization={selectedOrganization}
          tenants={visibleTenants}
          onInspectUser={setInspectedUser}
        />
      )}

      {!organizationsLoading && !selectedOrganization && (
        <div className="glass rounded-xl p-5" style={{ border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
          This organization could not be loaded for your account.
        </div>
      )}

      {!organizationsLoading && selectedOrganization && tenantsLoading ? (
        <div className="glass rounded-xl p-4" style={{ border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
          Loading workspaces for {selectedOrganization.name}…
        </div>
      ) : null}

      {!organizationsLoading && selectedOrganization ? (
        <TenantWorkspaceManager
          key={selectedOrganization.id}
          mode="organizations"
          initialOrganizationId={selectedOrganization.id}
        />
      ) : null}

      <TenantAccessDrawer
        open={!!inspectedUser}
        user={inspectedUser}
        tenants={visibleTenants}
        onClose={() => setInspectedUser(null)}
      />
    </div>
  )
}
