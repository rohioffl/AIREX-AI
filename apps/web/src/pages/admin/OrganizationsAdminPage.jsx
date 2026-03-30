import { useCallback, useEffect, useMemo, useState } from 'react'
import { Building2, Globe, Layers, RefreshCcw } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import AccessMatrixView from '../../components/admin/AccessMatrixView'
import TenantAccessDrawer from '../../components/admin/TenantAccessDrawer'
import TenantWorkspaceManager from '../../components/admin/TenantWorkspaceManager'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizationTenants, fetchOrganizations } from '../../services/api'
import { getActiveOrganizationIdOverride, setActiveOrganizationIdOverride } from '../../utils/organizationScope'
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
  const location = useLocation()
  const auth = useAuth()
  const {
    organizations: authOrganizations = [],
    tenants: authTenants = [],
    organizationMemberships = [],
    activeOrganization = null,
  } = auth
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(
    () => new URLSearchParams(location.search).get('org_id') || getActiveOrganizationIdOverride() || activeOrganization?.id || ''
  )
  const [inspectedUser, setInspectedUser] = useState(null)
  const [remoteOrganizations, setRemoteOrganizations] = useState([])
  const [organizationTenants, setOrganizationTenants] = useState([])
  const [organizationsLoading, setOrganizationsLoading] = useState(true)
  const [tenantsLoading, setTenantsLoading] = useState(false)
  const [pageError, setPageError] = useState('')
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/dashboard'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Dashboard'
  const requestedOrganizationId = new URLSearchParams(location.search).get('org_id') || getActiveOrganizationIdOverride() || ''
  const organizations = useMemo(
    () => (remoteOrganizations.length ? remoteOrganizations : authOrganizations),
    [authOrganizations, remoteOrganizations]
  )

  const loadOrganizations = useCallback(async () => {
    setOrganizationsLoading(true)
    setPageError('')
    try {
      const data = await fetchOrganizations()
      const nextOrganizations = Array.isArray(data) ? data : []
      setRemoteOrganizations(nextOrganizations)
      setSelectedOrganizationId((current) => {
        if (
          requestedOrganizationId
          && nextOrganizations.some((org) => String(org.id) === String(requestedOrganizationId))
        ) {
          return requestedOrganizationId
        }
        if (current && nextOrganizations.some((org) => String(org.id) === String(current))) {
          return current
        }
        if (
          activeOrganization?.id
          && nextOrganizations.some((org) => String(org.id) === String(activeOrganization.id))
        ) {
          return activeOrganization.id
        }
        return nextOrganizations[0]?.id || ''
      })
    } catch {
      setRemoteOrganizations([])
      setPageError('Failed to load organizations.')
      setSelectedOrganizationId((current) => current || activeOrganization?.id || authOrganizations[0]?.id || '')
    } finally {
      setOrganizationsLoading(false)
    }
  }, [activeOrganization?.id, authOrganizations, requestedOrganizationId])

  const selectedOrganization = useMemo(() => {
    if (!selectedOrganizationId) {
      return organizations[0] || activeOrganization || null
    }
    return organizations.find((org) => String(org.id) === String(selectedOrganizationId)) || null
  }, [activeOrganization, organizations, selectedOrganizationId])

  const visibleTenants = organizationTenants
  const scopedOrganizationMemberships = useMemo(
    () => organizationMemberships.filter((membership) => String(membership.id) === String(selectedOrganization?.id)),
    [organizationMemberships, selectedOrganization?.id]
  )

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
    if (requestedOrganizationId) {
      setActiveOrganizationIdOverride(String(requestedOrganizationId))
    }
  }, [requestedOrganizationId])

  useEffect(() => {
    loadOrganizations()
  }, [loadOrganizations])

  useEffect(() => {
    if (!selectedOrganizationId && organizations.length > 0) {
      setSelectedOrganizationId(requestedOrganizationId || activeOrganization?.id || organizations[0]?.id || '')
    }
  }, [activeOrganization?.id, organizations, requestedOrganizationId, selectedOrganizationId])

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
        <SummaryCard label="Tenant Spaces" value={visibleTenants.length} icon={Layers} color="var(--brand-orange)" />
        <SummaryCard label="Scoped Memberships" value={scopedOrganizationMemberships.length} icon={Building2} color="var(--neon-indigo)" />
      </div>

      <div
        className="glass rounded-xl p-5 flex items-center justify-between gap-4 flex-wrap"
        style={{ border: '1px solid var(--border)' }}
      >
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Selected Organization
          </div>
          <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)', marginTop: 8 }}>
            {selectedOrganization?.name || 'No organization selected'}
          </p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Manage org members, review workspace inventory, and onboard tenant workspaces inside this organization only.
          </p>
          {pageError && (
            <p style={{ fontSize: 12, color: '#f87171', marginTop: 8 }}>
              {pageError}
            </p>
          )}
        </div>
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

      {organizations.length > 1 && (
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
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>{org.name}</option>
              ))}
            </select>
          </div>
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
          No accessible organizations found for this account.
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
