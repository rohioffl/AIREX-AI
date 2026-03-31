import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Users, Cloud, Building2, ChevronRight } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizationTenants } from '../../services/api'
import { getActiveOrganizationIdOverride, setActiveOrganizationIdOverride } from '../../utils/organizationScope'
import { isPlatformAdmin } from '../../utils/accessControl'
import TenantMembersPanel from '../../components/admin/TenantMembersPanel'
import CloudAccountsPage from './CloudAccountsPage'

const TABS = [
  { id: 'members', label: 'Members', icon: Users },
  { id: 'setup', label: 'Cloud Accounts', icon: Cloud },
]

function CloudSetupStages({ tenantId }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{
        border: '1px solid var(--border)',
        borderRadius: 10, overflow: 'hidden',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 16px',
          background: 'var(--bg-elevated)',
          borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cloud size={14} style={{ color: 'var(--neon-cyan)' }} />
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Cloud Accounts
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              — onboard AWS accounts and GCP projects. Monitoring integrations live on their own page.
            </span>
          </div>
        </div>

        <div style={{ padding: '16px' }}>
          <CloudAccountsPage tenantId={tenantId} embedded />
        </div>
      </div>
    </div>
  )
}

export default function TenantWorkspaceAdminPage() {
  const { organizationSlug: routeOrganizationSlug = '' } = useParams()
  const auth = useAuth()
  const { tenants = [], activeTenant = null, activeOrganization = null, organizations = [] } = auth
  const scopedOrganization = useMemo(() => {
    if (!routeOrganizationSlug) {
      return organizations.find((organization) => String(organization.id) === String(getActiveOrganizationIdOverride()))
        || activeOrganization
        || null
    }
    return organizations.find((organization) => (
      String(organization.slug) === String(routeOrganizationSlug)
      || String(organization.id) === String(routeOrganizationSlug)
    )) || null
  }, [activeOrganization, organizations, routeOrganizationSlug])
  const organizationId = scopedOrganization?.id || getActiveOrganizationIdOverride() || activeOrganization?.id || ''
  const organizationRouteKey = scopedOrganization?.slug || scopedOrganization?.id || routeOrganizationSlug || organizationId || ''
  const backTarget = isPlatformAdmin(auth)
    ? '/admin'
    : organizationRouteKey
      ? `/admin/organizations/${encodeURIComponent(organizationRouteKey)}`
      : '/admin/organizations'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Organizations'
  const [scopedTenants, setScopedTenants] = useState([])
  const [loading, setLoading] = useState(Boolean(organizationId))

  const loadScopedTenants = useCallback(async () => {
    if (!organizationId) {
      setScopedTenants([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await fetchOrganizationTenants(organizationId)
      setScopedTenants(Array.isArray(data) ? data : [])
    } catch {
      setScopedTenants([])
    } finally {
      setLoading(false)
    }
  }, [organizationId])

  useEffect(() => {
    if (organizationId) {
      setActiveOrganizationIdOverride(String(organizationId))
    }
  }, [organizationId])

  useEffect(() => {
    loadScopedTenants()
  }, [loadScopedTenants])

  const allTenants = useMemo(() => {
    if (organizationId) {
      return scopedTenants
    }
    if (tenants.length) return tenants
    if (activeTenant) return [activeTenant]
    return []
  }, [organizationId, scopedTenants, tenants, activeTenant])

  const [selectedId, setSelectedId] = useState(() => activeTenant?.id || allTenants[0]?.id || '')
  const [activeTab, setActiveTab] = useState('members')

  useEffect(() => {
    if (!allTenants.length) {
      setSelectedId('')
      return
    }
    if (!allTenants.some((tenant) => String(tenant.id) === String(selectedId))) {
      setSelectedId(allTenants[0]?.id || '')
    }
  }, [allTenants, selectedId])

  const selectedTenant = useMemo(
    () => allTenants.find((tenant) => tenant.id === selectedId) || allTenants[0] || null,
    [allTenants, selectedId],
  )

  function selectTenant(tenant) {
    setSelectedId(tenant.id)
    setActiveTab('members')
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em', margin: 0 }}>
            Workspaces
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Select a workspace to manage its members, cloud accounts, and monitoring integrations.
          </p>
        </div>
        <Link
          to={backTarget}
          className="px-4 py-2 rounded-lg text-sm font-semibold"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', textDecoration: 'none' }}
        >
          {backLabel}
        </Link>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, alignItems: 'flex-start' }}>
        <div className="glass rounded-xl" style={{ border: '1px solid var(--border)', overflow: 'hidden' }}>
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Workspaces ({allTenants.length})
          </div>
          {loading ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
              Loading workspaces…
            </div>
          ) : allTenants.length === 0 ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
              No workspaces found
            </div>
          ) : (
            <div>
              {allTenants.map((tenant) => {
                const isActive = tenant.id === selectedTenant?.id
                return (
                  <button
                    key={tenant.id}
                    onClick={() => selectTenant(tenant)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '12px 14px',
                      background: isActive ? 'rgba(34,211,238,0.08)' : 'transparent',
                      borderLeft: `3px solid ${isActive ? 'var(--neon-cyan)' : 'transparent'}`,
                      border: 'none',
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <div
                      style={{
                        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                        background: isActive ? 'rgba(34,211,238,0.15)' : 'var(--bg-elevated)',
                        border: `1px solid ${isActive ? 'rgba(34,211,238,0.4)' : 'var(--border)'}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}
                    >
                      <Building2 size={14} style={{ color: isActive ? 'var(--neon-cyan)' : 'var(--text-muted)' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: isActive ? 'var(--text-heading)' : 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {tenant.display_name || tenant.name || tenant.slug}
                      </div>
                      {tenant.slug && (tenant.display_name || tenant.name) && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{tenant.slug}</div>
                      )}
                    </div>
                    {isActive && <ChevronRight size={14} style={{ color: 'var(--neon-cyan)', flexShrink: 0 }} />}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {selectedTenant ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div
              className="glass rounded-t-xl"
              style={{ padding: '14px 18px', borderBottom: 'none', border: '1px solid var(--border)', borderRadius: '10px 10px 0 0', display: 'flex', alignItems: 'center', gap: 10 }}
            >
              <Building2 size={16} style={{ color: 'var(--neon-cyan)' }} />
              <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)' }}>
                {selectedTenant.display_name || selectedTenant.name || selectedTenant.slug}
              </span>
              {selectedTenant.slug && (selectedTenant.display_name || selectedTenant.name) && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 4 }}>/ {selectedTenant.slug}</span>
              )}
            </div>

            <div style={{ display: 'flex', borderLeft: '1px solid var(--border)', borderRight: '1px solid var(--border)', borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
              {TABS.map((tab) => {
                const Icon = tab.icon
                const isActive = activeTab === tab.id
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '10px 18px',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: `2px solid ${isActive ? 'var(--neon-cyan)' : 'transparent'}`,
                      color: isActive ? 'var(--neon-cyan)' : 'var(--text-muted)',
                      fontSize: 13, fontWeight: isActive ? 600 : 400,
                      cursor: 'pointer',
                    }}
                  >
                    <Icon size={13} />
                    {tab.label}
                  </button>
                )
              })}
            </div>

            <div className="glass" style={{ border: '1px solid var(--border)', borderTop: 'none', borderRadius: '0 0 10px 10px', padding: 20 }}>
              {activeTab === 'members' && <TenantMembersPanel tenant={selectedTenant} />}
              {activeTab === 'setup' && <CloudSetupStages tenantId={selectedTenant.id} />}
            </div>
          </div>
        ) : (
          <div className="glass rounded-xl" style={{ border: '1px dashed var(--border)', padding: '64px 24px', textAlign: 'center' }}>
            <Building2 size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display: 'block', opacity: 0.3 }} />
            <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>Select a workspace to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}
