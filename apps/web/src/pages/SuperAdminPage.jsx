import { useEffect, useMemo, useState, useCallback } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  Building2, Edit, LayoutDashboard,
  Plus, Trash2, CheckCircle, AlertTriangle,
  ChevronRight, Server,
  ShieldCheck, Activity, X, UserCheck,
  Search, RefreshCcw, Globe, UserCog, Clock, ChevronDown,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useToasts } from '../context/ToastContext'
import ModalShell from '../components/common/ModalShell'
import TenantAccessDrawer from '../components/admin/TenantAccessDrawer'
import AccessMatrixView from '../components/admin/AccessMatrixView'
import {
  fetchTenants, fetchTenantDetail, createTenant, updateTenant, deleteTenant, reloadTenants,
  fetchOrganizations, createOrganization, createOrganizationTenant,
  fetchOrgMembers, addOrgMember, updateOrgMember, removeOrgMember,
  createProject, deleteProject,
  createIntegration, deleteIntegration, testIntegration,
  syncIntegrationMonitors, fetchIntegrationTypes,
  fetchBackendHealth,
  fetchUsers,
  fetchAuditEvents,
} from '../services/api'
import { useTenantWorkspace } from '../hooks/useTenantWorkspace'
import { extractErrorMessage } from '../utils/errorHandler'
import { FALLBACK_TENANT_ID } from '../utils/constants'

// ── Tab definitions ──────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview',  label: 'Overview',    icon: LayoutDashboard },
  { id: 'members',   label: 'Org Members', icon: UserCheck },
  { id: 'activity',  label: 'Activity',    icon: Clock },
]

// ── Shared helpers ────────────────────────────────────────────────────────────


function StatCard({ label, value, color = 'var(--neon-indigo)', icon: Icon, sub }) {
  return (
    <div className="glass rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
        {Icon && <Icon size={14} style={{ color, opacity: 0.7 }} />}
      </div>
      <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
      {sub && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sub}</span>}
    </div>
  )
}

function SectionHeader({ title, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{title}</span>
      {action}
    </div>
  )
}

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

function slugify(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab({ onNavigate }) {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [tenants, setTenants] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchBackendHealth().catch(() => null),
      fetchTenants().catch(() => []),
    ]).then(([h, t]) => {
      setHealth(h)
      setTenants(Array.isArray(t) ? t : [])
    }).finally(() => setLoading(false))
  }, [])

  const STATUS = [
    { label: 'Backend API',   ok: health?.status === 'ok',  detail: 'FastAPI + Uvicorn' },
    { label: 'Database',      ok: true,                      detail: 'PostgreSQL 15 + RLS' },
    { label: 'Redis / Queue', ok: true,                      detail: 'ARQ Worker' },
    { label: 'AI Engine',     ok: true,                      detail: 'Gemini 2.0 Flash' },
  ]

  return (
    <div className="space-y-6">
      {/* System Health */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="System Health" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {STATUS.map(s => (
            <div key={s.label} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              {loading ? (
                <div className="w-4 h-4 rounded-full animate-pulse" style={{ background: 'var(--border)' }} />
              ) : s.ok ? (
                <CheckCircle size={16} style={{ color: 'var(--neon-green)', flexShrink: 0 }} />
              ) : (
                <AlertTriangle size={16} style={{ color: 'var(--brand-orange)', flexShrink: 0 }} />
              )}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{s.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Tenants"        value={tenants.length}                             color="var(--neon-cyan)" icon={Building2} sub="Configured" />
        <StatCard label="Total Servers"  value={tenants.reduce((s,t)=>s+(t.server_count||0),0)} color="var(--neon-green)" icon={Server}    sub="Across all tenants" />
      </div>

      {/* Quick Navigation */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {TABS.filter(t => t.id !== 'overview').map(tab => (
          <button
            key={tab.id}
            onClick={() => onNavigate(tab.id)}
            className="glass rounded-xl p-4 flex items-center gap-3 hover-lift transition-all text-left"
            style={{ border: '1px solid var(--border)', cursor: 'pointer' }}
          >
            <div className="p-2 rounded-lg" style={{ background: 'rgba(99,102,241,0.12)' }}>
              <tab.icon size={16} style={{ color: 'var(--neon-indigo)' }} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{tab.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {tab.id === 'members' && 'Manage organization members'}
              </div>
            </div>
            <ChevronRight size={14} style={{ color: 'var(--text-muted)', marginLeft: 'auto' }} />
          </button>
        ))}
      </div>

      {/* Session */}
      <div className="glass rounded-xl p-5">
        <SectionHeader title="Current Session" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: 'Tenant ID', value: (user?.tenantId || user?.tenant_id || FALLBACK_TENANT_ID), mono: true },
            { label: 'Logged in as', value: user?.email || '—', mono: false },
            { label: 'Role', value: (user?.role || '—').toUpperCase(), mono: true },
          ].map(item => (
            <div key={item.label} className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</div>
              <div style={{ fontFamily: item.mono ? 'var(--font-mono)' : 'inherit', fontSize: 12, color: 'var(--text-heading)', marginTop: 4, wordBreak: 'break-all' }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Tenants Tab ───────────────────────────────────────────────────────────────

const AWS_AUTH_METHODS = [
  { value: 'role_assume', label: 'Cross-Account Role Assumption', desc: 'Recommended — uses IAM trust policy' },
  { value: 'role_arn',    label: 'Explicit Role ARN',              desc: 'Paste the full role ARN' },
  { value: 'access_keys', label: 'Access Key + Secret Key',       desc: 'Static credentials' },
  { value: 'creds_file',  label: 'Credentials File (on server)',  desc: 'Path to credentials file' },
  { value: 'instance',    label: 'Instance Role',                  desc: 'No config needed — uses EC2 metadata' },
]

const GCP_AUTH_METHODS = [
  { value: 'sa_key',  label: 'Service Account Key File', desc: 'Path to JSON key on server' },
  { value: 'adc',     label: 'Application Default Credentials', desc: 'Uses gcloud auth' },
  { value: 'auto',    label: 'Automatic (GCE/GKE)',      desc: 'Uses instance metadata' },
]

function CloudBadge({ cloud }) {
  const isGcp = cloud === 'gcp'
  return (
    <span style={{
      background: isGcp ? 'rgba(52,211,153,0.12)' : 'rgba(251,191,36,0.12)',
      color: isGcp ? 'var(--neon-green)' : 'var(--color-accent-amber)',
      borderRadius: 999, padding: '4px 10px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
    }}>
      {cloud || 'unknown'}
    </span>
  )
}

function CredBadge({ status }) {
  const ok = status === 'configured'
  return (
    <span className="flex items-center gap-1" style={{ fontSize: 11, color: ok ? 'var(--neon-green)' : 'var(--color-accent-amber)' }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: ok ? 'var(--neon-green)' : 'var(--color-accent-amber)', display: 'inline-block' }} />
      {ok ? 'Credentials OK' : 'Missing creds'}
    </span>
  )
}

export function TenantsTab() {
  const { addToast } = useToasts()
  const [search, setSearch] = useState('')
  const [showOnboard, setShowOnboard] = useState(false)
  const [editingTenant, setEditingTenant] = useState(null)
  const [deletingTenant, setDeletingTenant] = useState(null)
  const [showCreateOrganization, setShowCreateOrganization] = useState(false)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [showCreateIntegration, setShowCreateIntegration] = useState(false)

  const toast = useCallback(
    (msg, type = 'success') => {
      addToast({
        title: type === 'error' ? 'Error' : 'Success',
        message: msg,
        severity: type === 'error' ? 'CRITICAL' : 'LOW',
      })
    },
    [addToast]
  )

  const {
    organizations,
    activeOrganizationId,
    tenants,
    selectedTenantId,
    selectedTenant,
    projects,
    integrations,
    loading,
    detailLoading,
    setSelectedTenantId,
    changeOrganization,
    loadWorkspace,
    reloadWorkspace,
  } = useTenantWorkspace({
    onError: (message) => toast(message, 'error'),
  })

  const filtered = useMemo(() => {
    if (!search) return tenants
    const q = search.toLowerCase()
    return tenants.filter(t => t.name?.toLowerCase().includes(q) || t.display_name?.toLowerCase().includes(q) || t.cloud?.toLowerCase().includes(q))
  }, [tenants, search])

  const handleReload = async () => {
    try {
      const res = await reloadTenants()
      toast(`Config reloaded from ${res.source || 'db'} — ${res.tenant_count} tenant(s)`)
      reloadWorkspace()
    } catch (err) { toast(extractErrorMessage(err) || 'Reload failed', 'error') }
  }

  const handleDelete = async () => {
    if (!deletingTenant) return
    try {
      await deleteTenant(deletingTenant.name)
      toast(`Tenant "${deletingTenant.display_name}" deleted`)
      setDeletingTenant(null)
      reloadWorkspace()
    } catch (err) { toast(extractErrorMessage(err) || 'Delete failed', 'error') }
  }

  const openEdit = async (t) => {
    try {
      const detail = await fetchTenantDetail(t.name)
      setEditingTenant(detail)
    } catch { toast('Failed to load tenant detail', 'error') }
  }

  const handleDeleteProject = async (project) => {
    if (!window.confirm(`Delete project "${project.name}" from ${selectedTenant?.display_name || 'this tenant'}?`)) return
    try {
      await deleteProject(project.id)
      toast(`Project "${project.name}" deleted`)
      loadWorkspace(selectedTenantId)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Project delete failed', 'error')
    }
  }

  const handleTestIntegration = async (integration) => {
    try {
      await testIntegration(integration.id)
      toast(`Integration "${integration.name}" verified`)
      loadWorkspace(selectedTenantId)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Integration test failed', 'error')
    }
  }

  const handleSyncIntegration = async (integration) => {
    try {
      const result = await syncIntegrationMonitors(integration.id, [])
      toast(`Integration synced — ${result.monitor_count || 0} monitor(s) updated`)
      loadWorkspace(selectedTenantId)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Integration sync failed', 'error')
    }
  }

  const handleDeleteIntegration = async (integration) => {
    if (!window.confirm(`Disable integration "${integration.name}"?`)) return
    try {
      await deleteIntegration(integration.id)
      toast(`Integration "${integration.name}" disabled`)
      loadWorkspace(selectedTenantId)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Integration delete failed', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Organizations" value={organizations.length} color="var(--neon-purple)" icon={ShieldCheck} />
        <StatCard label="Total Tenants" value={tenants.length} color="var(--neon-indigo)" icon={Building2} />
        <StatCard label="Cloud Providers" value={[...new Set(tenants.map(t => t.cloud))].filter(Boolean).length} color="var(--neon-cyan)" icon={Globe} />
        <StatCard label="Total Servers" value={tenants.reduce((s, t) => s + (t.server_count || 0), 0)} color="var(--neon-green)" icon={Server} />
      </div>

      <div className="flex justify-between items-center gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap flex-1 min-w-[240px]">
          <select
            value={activeOrganizationId || ''}
            onChange={(e) => changeOrganization(e.target.value || null)}
            style={{ ...inputCls, maxWidth: 280 }}
          >
            <option value="">All accessible tenants</option>
            {organizations.map(org => (
              <option key={org.id} value={org.id}>{org.name}</option>
            ))}
          </select>

          <div style={{ position: 'relative', flex: '1 1 220px', maxWidth: 320 }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tenants…" style={{ ...inputCls, paddingLeft: 34 }} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowCreateOrganization(true)} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
            <ShieldCheck size={14} /> Add Organization
          </button>
          <button onClick={handleReload} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
            <RefreshCcw size={14} /> Reload Config
          </button>
          <button onClick={() => setShowOnboard(true)} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'var(--gradient-primary)' }}>
            <Plus size={14} /> Onboard Tenant
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="glass rounded-xl h-16 skeleton" />)}</div>
      ) : filtered.length === 0 ? (
        <div className="glass rounded-xl py-12 text-center" style={{ color: 'var(--text-muted)', fontSize: 14 }}>{search ? 'No tenants match your search' : 'No tenants configured'}</div>
      ) : (
        <div className="space-y-3">
          {filtered.map(t => (
            <div
              key={t.id || t.name}
              className="glass rounded-xl p-4 flex items-center justify-between cursor-pointer transition-all"
              style={{
                border: selectedTenantId === t.id ? '1px solid rgba(99,102,241,0.45)' : '1px solid transparent',
                boxShadow: selectedTenantId === t.id ? '0 0 0 1px rgba(99,102,241,0.1)' : 'none',
              }}
              onClick={() => setSelectedTenantId(t.id || null)}
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--glow-indigo)' }}>
                  <Building2 size={18} style={{ color: 'var(--neon-indigo)' }} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{t.display_name}</div>
                  <div className="flex items-center gap-2" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{t.name}</span>
                    {t.organization_name && <span>· {t.organization_name}</span>}
                    {t.escalation_email && <span>· {t.escalation_email}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <CredBadge status={t.credential_status} />
                <div className="text-right">
                  <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--neon-cyan)', fontFamily: 'var(--font-mono)' }}>{t.server_count ?? 0}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>servers</div>
                </div>
                <CloudBadge cloud={t.cloud} />
                <div className="flex items-center gap-1">
                  <button onClick={(event) => { event.stopPropagation(); openEdit(t) }} className="p-2 rounded-lg" style={{ background: 'transparent' }} title="Edit">
                    <Edit size={14} style={{ color: 'var(--text-muted)' }} />
                  </button>
                  <button onClick={(event) => { event.stopPropagation(); setDeletingTenant(t) }} className="p-2 rounded-lg" style={{ background: 'transparent' }} title="Delete">
                    <Trash2 size={14} style={{ color: 'var(--color-accent-amber)' }} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="glass rounded-xl p-5 space-y-4">
          <SectionHeader
            title={`Projects${selectedTenant ? ` · ${selectedTenant.display_name}` : ''}`}
            action={(
              <button
                onClick={() => setShowCreateProject(true)}
                disabled={!selectedTenant}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm disabled:opacity-50"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <Plus size={14} /> Add Project
              </button>
            )}
          />
          {detailLoading ? (
            <div className="space-y-2">{[1,2].map(i => <div key={i} className="rounded-xl h-14 skeleton" style={{ background: 'var(--bg-input)' }} />)}</div>
          ) : !selectedTenant ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Select a tenant to manage its projects.</div>
          ) : projects.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No projects configured for this tenant yet.</div>
          ) : (
            <div className="space-y-2">
              {projects.map(project => (
                <div key={project.id} className="flex items-center justify-between rounded-xl p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{project.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{project.slug}</span>
                      {project.description ? <span> · {project.description}</span> : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span style={{ fontSize: 11, color: project.is_active ? 'var(--neon-green)' : 'var(--text-muted)' }}>
                      {project.is_active ? 'Active' : 'Disabled'}
                    </span>
                    <button onClick={() => handleDeleteProject(project)} className="p-2 rounded-lg" style={{ background: 'transparent' }} title="Delete project">
                      <Trash2 size={14} style={{ color: 'var(--color-accent-amber)' }} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="glass rounded-xl p-5 space-y-4">
          <SectionHeader
            title={`Integrations${selectedTenant ? ` · ${selectedTenant.display_name}` : ''}`}
            action={(
              <button
                onClick={() => setShowCreateIntegration(true)}
                disabled={!selectedTenant}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm disabled:opacity-50"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <Plus size={14} /> Add Integration
              </button>
            )}
          />
          {detailLoading ? (
            <div className="space-y-2">{[1,2].map(i => <div key={i} className="rounded-xl h-14 skeleton" style={{ background: 'var(--bg-input)' }} />)}</div>
          ) : !selectedTenant ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Select a tenant to manage integrations.</div>
          ) : integrations.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No integrations configured for this tenant yet.</div>
          ) : (
            <div className="space-y-2">
              {integrations.map(integration => (
                <div key={integration.id} className="rounded-xl p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{integration.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{integration.slug}</span>
                        <span> · {integration.integration_type_key || integration.integration_type_id}</span>
                      </div>
                    </div>
                    <span style={{ fontSize: 11, color: integration.enabled ? 'var(--neon-green)' : 'var(--text-muted)' }}>
                      {integration.status || 'configured'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <button onClick={() => handleTestIntegration(integration)} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'rgba(52,211,153,0.08)', color: 'var(--neon-green)', border: '1px solid rgba(52,211,153,0.18)' }}>
                      Verify
                    </button>
                    <button onClick={() => handleSyncIntegration(integration)} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'rgba(56,189,248,0.08)', color: 'var(--neon-cyan)', border: '1px solid rgba(56,189,248,0.18)' }}>
                      Sync Monitors
                    </button>
                    <button onClick={() => handleDeleteIntegration(integration)} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'rgba(251,191,36,0.08)', color: 'var(--color-accent-amber)', border: '1px solid rgba(251,191,36,0.18)' }}>
                      Disable
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showOnboard && <TenantOnboardModal organizationId={activeOrganizationId} onClose={() => setShowOnboard(false)} onSaved={() => { setShowOnboard(false); reloadWorkspace() }} />}
      {editingTenant && <TenantEditDrawer tenant={editingTenant} onClose={() => setEditingTenant(null)} onSaved={() => { setEditingTenant(null); reloadWorkspace() }} />}
      {showCreateOrganization && <OrganizationCreateModal onClose={() => setShowCreateOrganization(false)} onSaved={() => { setShowCreateOrganization(false); reloadWorkspace() }} />}
      {showCreateProject && selectedTenant && <ProjectCreateModal tenant={selectedTenant} onClose={() => setShowCreateProject(false)} onSaved={() => { setShowCreateProject(false); loadWorkspace(selectedTenant.id) }} />}
      {showCreateIntegration && selectedTenant && <IntegrationCreateModal tenant={selectedTenant} onClose={() => setShowCreateIntegration(false)} onSaved={() => { setShowCreateIntegration(false); loadWorkspace(selectedTenant.id) }} />}
      {deletingTenant && (
        <ModalShell onClose={() => setDeletingTenant(null)} title="Delete Tenant" maxWidth="max-w-sm" panelClassName="space-y-4">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              Are you sure you want to delete <strong>{deletingTenant.display_name}</strong>? This will deactivate the tenant configuration.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeletingTenant(null)} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
              <button onClick={handleDelete} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'var(--color-danger, #ef4444)' }}>Delete</button>
            </div>
        </ModalShell>
      )}
    </div>
  )
}

// ── Tenant Edit Drawer ──────────────────────────────────────────────────────

function TenantEditDrawer({ tenant, onClose, onSaved }) {
  const { addToast } = useToasts()
  const [form, setForm] = useState({ ...tenant })
  const [saving, setSaving] = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateTenant(tenant.name, {
        display_name: form.display_name,
        cloud: form.cloud,
        escalation_email: form.escalation_email,
        slack_channel: form.slack_channel,
        ssh_user: form.ssh_user,
        aws_config: form.aws_config,
        gcp_config: form.gcp_config,
      })
      toast('Tenant updated successfully')
      onSaved()
    } catch (err) { toast(extractErrorMessage(err) || 'Update failed', 'error') } finally { setSaving(false) }
  }

  const upd = (key, val) => setForm(f => ({ ...f, [key]: val }))
  const updAws = (key, val) => setForm(f => ({ ...f, aws_config: { ...f.aws_config, [key]: val } }))
  const updGcp = (key, val) => setForm(f => ({ ...f, gcp_config: { ...f.gcp_config, [key]: val } }))

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }} onClick={onClose} />
      <div className="relative w-full max-w-lg glass p-6 space-y-4 overflow-y-auto" style={{ maxHeight: '100vh' }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>Edit: {tenant.display_name}</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="space-y-3">
          <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Display Name</label>
            <input value={form.display_name || ''} onChange={e => upd('display_name', e.target.value)} style={inputCls} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Cloud</label>
              <select value={form.cloud || 'aws'} onChange={e => upd('cloud', e.target.value)} style={inputCls}><option value="aws">AWS</option><option value="gcp">GCP</option></select></div>
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>SSH User</label>
              <input value={form.ssh_user || ''} onChange={e => upd('ssh_user', e.target.value)} style={inputCls} /></div>
          </div>
          <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Escalation Email</label>
            <input value={form.escalation_email || ''} onChange={e => upd('escalation_email', e.target.value)} style={inputCls} /></div>
          <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slack Channel</label>
            <input value={form.slack_channel || ''} onChange={e => upd('slack_channel', e.target.value)} style={inputCls} /></div>

          {form.cloud === 'aws' && (
            <div className="space-y-2 p-3 rounded-xl" style={{ background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.15)' }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-accent-amber)' }}>AWS Config</span>
              <div className="grid grid-cols-2 gap-2">
                <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Account ID</label><input value={form.aws_config?.account_id || ''} onChange={e => updAws('account_id', e.target.value)} style={{ ...inputCls, fontSize: 12 }} /></div>
                <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Role Name</label><input value={form.aws_config?.role_name || ''} onChange={e => updAws('role_name', e.target.value)} style={{ ...inputCls, fontSize: 12 }} /></div>
                <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>External ID</label><input value={form.aws_config?.external_id || ''} onChange={e => updAws('external_id', e.target.value)} style={{ ...inputCls, fontSize: 12 }} /></div>
                <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Region</label><input value={form.aws_config?.region || ''} onChange={e => updAws('region', e.target.value)} style={{ ...inputCls, fontSize: 12 }} /></div>
              </div>
            </div>
          )}
          {form.cloud === 'gcp' && (
            <div className="space-y-2 p-3 rounded-xl" style={{ background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.15)' }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--neon-green)' }}>GCP Config</span>
              <div className="grid grid-cols-2 gap-2">
                <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Project ID</label><input value={form.gcp_config?.project_id || ''} onChange={e => updGcp('project_id', e.target.value)} style={{ ...inputCls, fontSize: 12 }} /></div>
                <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>SA Key Path</label><input value={form.gcp_config?.service_account_key || ''} onChange={e => updGcp('service_account_key', e.target.value)} style={{ ...inputCls, fontSize: 12 }} /></div>
              </div>
            </div>
          )}
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tenant Onboard Wizard (4 steps) ─────────────────────────────────────────

function TenantOnboardModal({ organizationId = null, onClose, onSaved }) {
  const { addToast } = useToasts()
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [awsAuth, setAwsAuth] = useState('role_assume')
  const [gcpAuth, setGcpAuth] = useState('sa_key')

  const [form, setForm] = useState({
    display_name: '', name: '', cloud: 'aws', escalation_email: '', slack_channel: '',
    ssh_user: 'ubuntu',
    aws_config: { account_id: '', role_name: '', role_arn: '', external_id: '', access_key_id: '', secret_access_key: '', credentials_file: '', region: '' },
    gcp_config: { project_id: '', service_account_key: '' },
  })

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const upd = (key, val) => setForm(f => ({ ...f, [key]: val }))
  const updAws = (key, val) => setForm(f => ({ ...f, aws_config: { ...f.aws_config, [key]: val } }))
  const updGcp = (key, val) => setForm(f => ({ ...f, gcp_config: { ...f.gcp_config, [key]: val } }))

  const steps = ['Basic Info', 'Cloud Credentials', 'SSH & Defaults', 'Review']

  const canNext = () => {
    if (step === 0) return form.display_name && form.name
    return true
  }

  const handleCreate = async () => {
    setSaving(true)
    try {
      if (organizationId) {
        await createOrganizationTenant(organizationId, form)
      } else {
        await createTenant({ ...form, organization_id: organizationId })
      }
      toast(`Tenant "${form.display_name}" created successfully`)
      onSaved()
    } catch (err) { toast(extractErrorMessage(err) || 'Create failed', 'error') } finally { setSaving(false) }
  }

  return (
    <ModalShell
      onClose={onClose}
      title="Onboard New Tenant"
      subtitle={`Step ${step + 1} of ${steps.length}`}
      maxWidth="max-w-lg"
      panelClassName="space-y-5 overflow-y-auto"
      panelStyle={{ maxHeight: '90vh' }}
    >
        <div className="flex items-center justify-end">
          <button onClick={onClose} aria-label="Close onboard tenant modal"><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>

        {/* Progress */}
        <div className="flex items-center gap-1">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-1" style={{ flex: 1 }}>
              <div style={{
                width: 22, height: 22, borderRadius: '50%', fontSize: 11, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: i <= step ? 'var(--neon-indigo)' : 'var(--bg-input)', color: i <= step ? '#fff' : 'var(--text-muted)',
              }}>{i < step ? '✓' : i + 1}</div>
              <span style={{ fontSize: 10, color: i <= step ? 'var(--text-heading)' : 'var(--text-muted)', whiteSpace: 'nowrap' }}>{s}</span>
              {i < steps.length - 1 && <div style={{ flex: 1, height: 1, background: i < step ? 'var(--neon-indigo)' : 'var(--border)', margin: '0 4px' }} />}
            </div>
          ))}
        </div>

        {/* Step 0: Basic Info */}
        {step === 0 && (
          <div className="space-y-3">
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Display Name *</label>
              <input value={form.display_name} onChange={e => { upd('display_name', e.target.value); if (!form.name || form.name === slugify(form.display_name)) upd('name', slugify(e.target.value)) }} placeholder="Acme Corporation" style={inputCls} /></div>
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug (URL-safe identifier) *</label>
              <input value={form.name} onChange={e => upd('name', slugify(e.target.value))} placeholder="acme-corp" style={{ ...inputCls, fontFamily: 'var(--font-mono)' }} /></div>
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Cloud Provider *</label>
              <select value={form.cloud} onChange={e => upd('cloud', e.target.value)} style={inputCls}><option value="aws">AWS</option><option value="gcp">GCP</option></select></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Escalation Email</label>
                <input value={form.escalation_email} onChange={e => upd('escalation_email', e.target.value)} placeholder="sre@acme.com" style={inputCls} /></div>
              <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slack Channel</label>
                <input value={form.slack_channel} onChange={e => upd('slack_channel', e.target.value)} placeholder="#acme-alerts" style={inputCls} /></div>
            </div>
          </div>
        )}

        {/* Step 1: Cloud Credentials */}
        {step === 1 && form.cloud === 'aws' && (
          <div className="space-y-3">
            {AWS_AUTH_METHODS.map(m => (
              <div key={m.value} className="rounded-xl p-3" style={{ background: awsAuth === m.value ? 'rgba(251,191,36,0.06)' : 'transparent', border: awsAuth === m.value ? '1px solid rgba(251,191,36,0.2)' : '1px solid var(--border)', cursor: 'pointer' }} onClick={() => setAwsAuth(m.value)}>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="radio" checked={awsAuth === m.value} onChange={() => setAwsAuth(m.value)} style={{ marginTop: 3, accentColor: 'var(--color-accent-amber)' }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{m.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{m.desc}</div>
                  </div>
                </label>
                {awsAuth === m.value && m.value === 'role_assume' && (
                  <div className="grid grid-cols-2 gap-2 mt-3 ml-6">
                    <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Account ID *</label><input value={form.aws_config.account_id} onChange={e => updAws('account_id', e.target.value)} placeholder="123456789012" style={{ ...inputCls, fontSize: 12 }} /></div>
                    <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Role Name *</label><input value={form.aws_config.role_name} onChange={e => updAws('role_name', e.target.value)} placeholder="AirexReadOnly" style={{ ...inputCls, fontSize: 12 }} /></div>
                    <div className="col-span-2"><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>External ID <span style={{ opacity: 0.6 }}>(optional)</span></label><input value={form.aws_config.external_id} onChange={e => updAws('external_id', e.target.value)} placeholder="airex-trust-xyz" style={{ ...inputCls, fontSize: 12 }} /></div>
                  </div>
                )}
                {awsAuth === m.value && m.value === 'role_arn' && (
                  <div className="mt-3 ml-6"><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Role ARN *</label><input value={form.aws_config.role_arn} onChange={e => updAws('role_arn', e.target.value)} placeholder="arn:aws:iam::123456789012:role/AirexRole" style={{ ...inputCls, fontSize: 12 }} /></div>
                )}
                {awsAuth === m.value && m.value === 'access_keys' && (
                  <div className="space-y-2 mt-3 ml-6">
                    <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Access Key ID *</label><input value={form.aws_config.access_key_id} onChange={e => updAws('access_key_id', e.target.value)} placeholder="AKIAIOSFODNN7EXAMPLE" style={{ ...inputCls, fontSize: 12, fontFamily: 'var(--font-mono)' }} /></div>
                    <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Secret Access Key *</label><input type="password" value={form.aws_config.secret_access_key} onChange={e => updAws('secret_access_key', e.target.value)} placeholder="••••••••" style={{ ...inputCls, fontSize: 12, fontFamily: 'var(--font-mono)' }} /></div>
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'rgba(251,191,36,0.08)', fontSize: 11, color: 'var(--color-accent-amber)' }}>
                      <AlertTriangle size={13} /> Keys stored in DB. Use Role Assumption for production.
                    </div>
                  </div>
                )}
                {awsAuth === m.value && m.value === 'creds_file' && (
                  <div className="mt-3 ml-6"><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>File Path on Server *</label><input value={form.aws_config.credentials_file} onChange={e => updAws('credentials_file', e.target.value)} placeholder="/etc/airex/aws-creds.json" style={{ ...inputCls, fontSize: 12, fontFamily: 'var(--font-mono)' }} /></div>
                )}
                {awsAuth === m.value && m.value === 'instance' && (
                  <div className="mt-3 ml-6 px-3 py-2 rounded-lg" style={{ background: 'rgba(52,211,153,0.08)', fontSize: 11, color: 'var(--neon-green)' }}>
                    <CheckCircle size={13} style={{ display: 'inline', marginRight: 4 }} /> No credentials needed — AIREX will use the EC2 instance role.
                  </div>
                )}
              </div>
            ))}
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>AWS Region</label>
              <input value={form.aws_config.region} onChange={e => updAws('region', e.target.value)} placeholder="Leave empty for auto-discover" style={inputCls} /></div>
          </div>
        )}

        {step === 1 && form.cloud === 'gcp' && (
          <div className="space-y-3">
            {GCP_AUTH_METHODS.map(m => (
              <div key={m.value} className="rounded-xl p-3" style={{ background: gcpAuth === m.value ? 'rgba(52,211,153,0.06)' : 'transparent', border: gcpAuth === m.value ? '1px solid rgba(52,211,153,0.2)' : '1px solid var(--border)', cursor: 'pointer' }} onClick={() => setGcpAuth(m.value)}>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="radio" checked={gcpAuth === m.value} onChange={() => setGcpAuth(m.value)} style={{ marginTop: 3, accentColor: 'var(--neon-green)' }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{m.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{m.desc}</div>
                  </div>
                </label>
                {gcpAuth === m.value && m.value === 'sa_key' && (
                  <div className="grid grid-cols-2 gap-2 mt-3 ml-6">
                    <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Project ID *</label><input value={form.gcp_config.project_id} onChange={e => updGcp('project_id', e.target.value)} placeholder="my-project-123" style={{ ...inputCls, fontSize: 12 }} /></div>
                    <div><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Key File Path *</label><input value={form.gcp_config.service_account_key} onChange={e => updGcp('service_account_key', e.target.value)} placeholder="/etc/airex/sa.json" style={{ ...inputCls, fontSize: 12, fontFamily: 'var(--font-mono)' }} /></div>
                  </div>
                )}
                {gcpAuth === m.value && (m.value === 'adc' || m.value === 'auto') && (
                  <div className="mt-3 ml-6"><label style={{ fontSize: 10, color: 'var(--text-muted)' }}>Project ID *</label><input value={form.gcp_config.project_id} onChange={e => updGcp('project_id', e.target.value)} placeholder="my-project-123" style={{ ...inputCls, fontSize: 12 }} /></div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Step 2: SSH */}
        {step === 2 && (
          <div className="space-y-3">
            <div><label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Default SSH User</label>
              <input value={form.ssh_user} onChange={e => upd('ssh_user', e.target.value)} placeholder="ubuntu" style={inputCls} /></div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Per-server SSH overrides can be configured after tenant creation by editing the server list.</p>
          </div>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <div className="space-y-3">
            <div className="glass rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Name</span><span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{form.display_name}</span></div>
              <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Slug</span><span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-heading)' }}>{form.name}</span></div>
              <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Cloud</span><CloudBadge cloud={form.cloud} /></div>
              <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Auth Method</span><span style={{ fontSize: 12, color: 'var(--text-heading)' }}>{form.cloud === 'aws' ? (AWS_AUTH_METHODS.find(m => m.value === awsAuth)?.label || awsAuth) : (GCP_AUTH_METHODS.find(m => m.value === gcpAuth)?.label || gcpAuth)}</span></div>
              {form.escalation_email && <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Email</span><span style={{ fontSize: 12, color: 'var(--text-heading)' }}>{form.escalation_email}</span></div>}
              {form.slack_channel && <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Slack</span><span style={{ fontSize: 12, color: 'var(--text-heading)' }}>{form.slack_channel}</span></div>}
              <div className="flex items-center justify-between"><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>SSH User</span><span style={{ fontSize: 12, color: 'var(--text-heading)' }}>{form.ssh_user}</span></div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex gap-3 pt-2">
          {step > 0 ? (
            <button onClick={() => setStep(s => s - 1)} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Back</button>
          ) : (
            <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          )}
          {step < steps.length - 1 ? (
            <button onClick={() => setStep(s => s + 1)} disabled={!canNext()} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>Next</button>
          ) : (
            <button onClick={handleCreate} disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
              {saving ? 'Creating…' : 'Create Tenant'}
            </button>
          )}
        </div>
    </ModalShell>
  )
}

function OrganizationCreateModal({ onClose, onSaved }) {
  const { addToast } = useToasts()
  const [form, setForm] = useState({ name: '', slug: '' })
  const [saving, setSaving] = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const handleSave = async () => {
    setSaving(true)
    try {
      await createOrganization({ ...form, slug: slugify(form.slug || form.name) })
      toast(`Organization "${form.name}" created`)
      onSaved()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Organization create failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalShell onClose={onClose} title="Create Organization" maxWidth="max-w-md" panelClassName="space-y-4">
        <div className="flex items-center justify-end">
          <button onClick={onClose} aria-label="Close organization modal"><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Name</label>
          <input aria-label="Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value, slug: f.slug || slugify(e.target.value) }))} style={inputCls} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug</label>
          <input aria-label="Slug" value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} style={{ ...inputCls, fontFamily: 'var(--font-mono)' }} />
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving || !form.name.trim()} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Creating…' : 'Create Organization'}
          </button>
        </div>
    </ModalShell>
  )
}

function ProjectCreateModal({ tenant, onClose, onSaved }) {
  const { addToast } = useToasts()
  const [form, setForm] = useState({ name: '', slug: '', description: '' })
  const [saving, setSaving] = useState(false)

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  const handleSave = async () => {
    setSaving(true)
    try {
      await createProject(tenant.id, { ...form, slug: slugify(form.slug || form.name) })
      toast(`Project "${form.name}" created`)
      onSaved()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Project create failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalShell onClose={onClose} title="Create Project" subtitle={tenant.display_name} maxWidth="max-w-md" panelClassName="space-y-4">
        <div className="flex items-center justify-end">
          <button onClick={onClose} aria-label="Close project modal"><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Name</label>
          <input aria-label="Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value, slug: f.slug || slugify(e.target.value) }))} style={inputCls} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug</label>
          <input aria-label="Slug" value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} style={{ ...inputCls, fontFamily: 'var(--font-mono)' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Description</label>
          <input aria-label="Description" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} style={inputCls} />
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving || !form.name.trim()} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Creating…' : 'Create Project'}
          </button>
        </div>
    </ModalShell>
  )
}

function IntegrationCreateModal({ tenant, onClose, onSaved }) {
  const { addToast } = useToasts()
  const [types, setTypes] = useState([])
  const [loadingTypes, setLoadingTypes] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    integration_type_key: 'site24x7',
    name: '',
    slug: '',
    secret_ref: '',
    webhook_token_ref: '',
  })

  const toast = (msg, type = 'success') =>
    addToast({ title: type === 'error' ? 'Error' : 'Success', message: msg, severity: type === 'error' ? 'CRITICAL' : 'LOW' })

  useEffect(() => {
    fetchIntegrationTypes()
      .then(data => {
        const nextTypes = Array.isArray(data) ? data : []
        setTypes(nextTypes)
        if (nextTypes[0]?.key && !form.integration_type_key) {
          setForm(current => ({ ...current, integration_type_key: nextTypes[0].key }))
        }
      })
      .catch(() => toast('Failed to load integration types', 'error'))
      .finally(() => setLoadingTypes(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    setSaving(true)
    try {
      await createIntegration(tenant.id, {
        ...form,
        slug: slugify(form.slug || form.name),
        config_json: {},
      })
      toast(`Integration "${form.name}" created`)
      onSaved()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Integration create failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalShell onClose={onClose} title="Add Integration" subtitle={tenant.display_name} maxWidth="max-w-md" panelClassName="space-y-4">
        <div className="flex items-center justify-end">
          <button onClick={onClose} aria-label="Close integration modal"><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Integration Type</label>
          <select
            aria-label="Integration Type"
            value={form.integration_type_key}
            onChange={e => setForm(current => ({ ...current, integration_type_key: e.target.value }))}
            disabled={loadingTypes}
            style={inputCls}
          >
            {types.map(type => (
              <option key={type.id} value={type.key}>{type.display_name}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Name</label>
          <input aria-label="Name" value={form.name} onChange={e => setForm(current => ({ ...current, name: e.target.value, slug: current.slug || slugify(e.target.value) }))} style={inputCls} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Slug</label>
          <input aria-label="Slug" value={form.slug} onChange={e => setForm(current => ({ ...current, slug: e.target.value }))} style={{ ...inputCls, fontFamily: 'var(--font-mono)' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Secret Ref</label>
          <input aria-label="Secret Ref" value={form.secret_ref} onChange={e => setForm(current => ({ ...current, secret_ref: e.target.value }))} placeholder="secret://provider/api-token" style={inputCls} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Webhook Token Ref</label>
          <input aria-label="Webhook Token Ref" value={form.webhook_token_ref} onChange={e => setForm(current => ({ ...current, webhook_token_ref: e.target.value }))} placeholder="secret://provider/webhook" style={inputCls} />
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>Cancel</button>
          <button onClick={handleSave} disabled={saving || !form.name.trim()} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-60" style={{ background: 'var(--gradient-primary)' }}>
            {saving ? 'Creating…' : 'Create Integration'}
          </button>
        </div>
    </ModalShell>
  )
}
// ── Org Members Tab ───────────────────────────────────────────────────────────

function MembersTab() {
  const [orgs, setOrgs] = useState([])
  const [selectedOrgId, setSelectedOrgId] = useState('')
  const [members, setMembers] = useState([])
  const [users, setUsers] = useState([])
  const [tenants, setTenants] = useState([])
  const [loading, setLoading] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [addUserId, setAddUserId] = useState('')
  const [addRole, setAddRole] = useState('operator')
  const [saving, setSaving] = useState(false)
  const [drawerUser, setDrawerUser] = useState(null)
  const [showMatrix, setShowMatrix] = useState(false)
  const { addToast } = useToasts()

  useEffect(() => {
    fetchOrganizations().then(setOrgs).catch(() => {})
    fetchUsers().then(data => setUsers(Array.isArray(data) ? data : (data.items || []))).catch(() => {})
    fetchTenants().then(data => setTenants(Array.isArray(data) ? data : (data.items || []))).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedOrgId) { setMembers([]); return }
    setLoading(true)
    fetchOrgMembers(selectedOrgId)
      .then(setMembers)
      .catch(() => addToast('error', 'Failed to load members'))
      .finally(() => setLoading(false))
  }, [selectedOrgId])

  function userName(userId) {
    const u = users.find(x => String(x.id) === String(userId))
    return u ? (u.display_name || u.email || String(userId)) : String(userId).slice(0, 8) + '…'
  }

  async function handleAdd() {
    if (!addUserId || !selectedOrgId) return
    setSaving(true)
    try {
      const m = await addOrgMember(selectedOrgId, { user_id: addUserId, role: addRole })
      setMembers(prev => [...prev, m])
      setShowAdd(false)
      setAddUserId('')
      setAddRole('operator')
      addToast('success', 'Member added')
    } catch (e) {
      addToast('error', extractErrorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function handleRoleChange(userId, role) {
    try {
      const m = await updateOrgMember(selectedOrgId, userId, { role })
      setMembers(prev => prev.map(x => String(x.user_id) === String(userId) ? { ...x, role: m.role } : x))
    } catch (e) {
      addToast('error', extractErrorMessage(e))
    }
  }

  async function handleRemove(userId) {
    try {
      await removeOrgMember(selectedOrgId, userId)
      setMembers(prev => prev.filter(x => String(x.user_id) !== String(userId)))
      addToast('success', 'Member removed')
    } catch (e) {
      addToast('error', extractErrorMessage(e))
    }
  }

  const nonMembers = users.filter(u => !members.some(m => String(m.user_id) === String(u.id)))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <SectionHeader title="Organization Members" />
        {selectedOrgId && (
          <button
            onClick={() => setShowMatrix(s => !s)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
            style={{ background: 'rgba(139,92,246,0.1)', color: 'var(--neon-violet)', border: '1px solid rgba(139,92,246,0.2)' }}
          >
            <ShieldCheck size={12} /> {showMatrix ? 'Hide Matrix' : 'Access Matrix'}
          </button>
        )}
      </div>

      <div className="glass rounded-xl p-4 space-y-3">
        <div>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Select Organization</label>
          <select value={selectedOrgId} onChange={e => setSelectedOrgId(e.target.value)} style={inputCls}>
            <option value="">Choose an organization…</option>
            {orgs.map(o => <option key={o.id} value={o.id}>{o.name} ({o.slug})</option>)}
          </select>
        </div>
      </div>

      {selectedOrgId && (
        <div className="glass rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
              Members ({members.length})
            </span>
            <button
              onClick={() => setShowAdd(s => !s)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
              style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--neon-indigo)', border: '1px solid rgba(99,102,241,0.2)' }}
            >
              <Plus size={12} /> Add Member
            </button>
          </div>

          {showAdd && (
            <div className="flex items-end gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div className="flex-1">
                <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>User</label>
                <select value={addUserId} onChange={e => setAddUserId(e.target.value)} style={inputCls}>
                  <option value="">Select user…</option>
                  {nonMembers.map(u => (
                    <option key={u.id} value={u.id}>{u.display_name || u.email}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Role</label>
                <select value={addRole} onChange={e => setAddRole(e.target.value)} style={{ ...inputCls, width: 130 }}>
                  <option value="viewer">Viewer</option>
                  <option value="operator">Operator</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <button
                onClick={handleAdd}
                disabled={!addUserId || saving}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50 transition-all"
                style={{ background: 'var(--gradient-primary)', flexShrink: 0 }}
              >
                <Plus size={12} /> {saving ? 'Adding…' : 'Add'}
              </button>
              <button onClick={() => setShowAdd(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4, flexShrink: 0 }}>
                <X size={14} />
              </button>
            </div>
          )}

          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>
          ) : members.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: 13 }}>No members yet</div>
          ) : (
            <div className="space-y-2">
              {members.map(m => (
                <div key={m.id} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0" style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--neon-indigo)', fontWeight: 700, fontSize: 11 }}>
                    {userName(m.user_id).charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{userName(m.user_id)}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>{String(m.user_id).slice(0, 8)}…</div>
                  </div>
                  <select
                    value={m.role}
                    onChange={e => handleRoleChange(m.user_id, e.target.value)}
                    style={{ ...inputCls, width: 120, fontSize: 12, padding: '4px 8px' }}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="operator">Operator</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    onClick={() => setDrawerUser(users.find(u => String(u.id) === String(m.user_id)) || { id: m.user_id, display_name: userName(m.user_id) })}
                    title="Manage tenant access"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--neon-indigo)', padding: 4, flexShrink: 0, opacity: 0.8 }}
                    className="transition-opacity hover:opacity-100"
                  >
                    <UserCog size={14} />
                  </button>
                  <button
                    onClick={() => handleRemove(m.user_id)}
                    title="Remove member"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-accent-red)', padding: 4, flexShrink: 0, opacity: 0.7 }}
                    className="transition-opacity hover:opacity-100"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Access Matrix */}
      {showMatrix && selectedOrgId && (
        <AccessMatrixView
          organization={orgs.find(o => String(o.id) === String(selectedOrgId))}
          tenants={tenants.filter(t => String(t.organization_id) === String(selectedOrgId))}
          onInspectUser={(user) => setDrawerUser(user)}
        />
      )}

      {/* Tenant Access Drawer */}
      <TenantAccessDrawer
        user={drawerUser}
        tenants={tenants.filter(t => String(t.organization_id) === String(selectedOrgId))}
        open={!!drawerUser}
        onClose={() => setDrawerUser(null)}
      />
    </div>
  )
}

// ── Activity Tab ──────────────────────────────────────────────────────────────

const ACTION_COLOR = {
  org_member_added: 'var(--neon-green)',
  org_member_removed: '#ef4444',
  org_member_role_changed: 'var(--neon-indigo)',
  tenant_member_added: 'var(--neon-cyan)',
  tenant_member_removed: '#ef4444',
  integration_created: 'var(--neon-purple)',
  integration_deleted: '#ef4444',
  incident_approved: 'var(--neon-green)',
  incident_rejected: '#ef4444',
}

function ActivityTab() {
  const [orgs, setOrgs] = useState([])
  const [selectedOrgId, setSelectedOrgId] = useState('')
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [actionFilter, setActionFilter] = useState('')

  useEffect(() => {
    fetchOrganizations().then(setOrgs).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedOrgId) { setEvents([]); return }
    setLoading(true)
    fetchAuditEvents(selectedOrgId, { action: actionFilter || undefined, limit: 100 })
      .then(data => setEvents(Array.isArray(data) ? data : []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [selectedOrgId, actionFilter])

  const uniqueActions = useMemo(() => [...new Set(events.map(e => e.action))].sort(), [events])

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Audit Trail
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            Append-only log of all org-level actions — member changes, integration events, and incident decisions.
          </p>
        </div>

        <div className="flex flex-wrap gap-3 items-end">
          <div style={{ minWidth: 200 }}>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Organization</label>
            <select
              value={selectedOrgId}
              onChange={e => { setSelectedOrgId(e.target.value); setActionFilter('') }}
              style={inputCls}
            >
              <option value="">Select organization…</option>
              {orgs.map(org => (
                <option key={org.id} value={org.id}>{org.name}</option>
              ))}
            </select>
          </div>
          {selectedOrgId && uniqueActions.length > 0 && (
            <div style={{ minWidth: 200 }}>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Filter by Action</label>
              <select value={actionFilter} onChange={e => setActionFilter(e.target.value)} style={inputCls}>
                <option value="">All actions</option>
                {uniqueActions.map(a => (
                  <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {!selectedOrgId && (
          <div className="rounded-xl p-4 text-center" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)', color: 'var(--text-muted)', fontSize: 13 }}>
            Select an organization to view its audit trail.
          </div>
        )}

        {selectedOrgId && loading && (
          <div className="space-y-2">
            {[1,2,3].map(i => <div key={i} className="h-12 rounded-xl skeleton" />)}
          </div>
        )}

        {selectedOrgId && !loading && events.length === 0 && (
          <div className="rounded-xl p-4 text-center" style={{ background: 'var(--bg-input)', border: '1px dashed var(--border)', color: 'var(--text-muted)', fontSize: 13 }}>
            No audit events recorded yet.
          </div>
        )}

        {selectedOrgId && !loading && events.length > 0 && (
          <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
              <thead style={{ background: 'var(--bg-elevated)' }}>
                <tr>
                  {['Action', 'Actor', 'Entity', 'IP', 'When'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '10px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map(ev => (
                  <tr key={ev.id} style={{ background: 'var(--bg-input)' }}>
                    <td style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: ACTION_COLOR[ev.action] || 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        {ev.action.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ev.actor_email || '—'}</div>
                      {ev.actor_role && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>{ev.actor_role}</div>}
                    </td>
                    <td style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                      {ev.entity_type && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {ev.entity_type}{ev.entity_id ? `:${ev.entity_id.slice(0, 8)}…` : ''}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{ev.ip_address || '—'}</span>
                    </td>
                    <td style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {new Date(ev.created_at).toLocaleString()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SuperAdminPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab') || 'overview'
  const activeTab = TABS.some((tab) => tab.id === requestedTab) ? requestedTab : 'overview'

  const setTab = (id) => setSearchParams(id === 'overview' ? {} : { tab: id })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="p-3 rounded-xl" style={{ background: 'linear-gradient(135deg,rgba(99,102,241,0.15),rgba(139,92,246,0.1))', border: '1px solid rgba(99,102,241,0.2)' }}>
          <ShieldCheck size={22} style={{ color: 'var(--neon-indigo)' }} />
        </div>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>Organization Administration</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Overview · Org Members · Activity
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            to: '/admin/organizations',
            title: 'Organizations',
            desc: 'Customer orgs and tenant onboarding',
            icon: ShieldCheck,
            tint: 'rgba(167,139,250,0.14)',
            color: 'var(--neon-purple)',
          },
          {
            to: '/admin/workspaces',
            title: 'Tenant Workspaces',
            desc: 'Tenant structure, projects, and defaults',
            icon: Building2,
            tint: 'rgba(99,102,241,0.14)',
            color: 'var(--neon-indigo)',
          },
          {
            to: '/admin/integrations',
            title: 'Integrations',
            desc: 'Tenant-owned monitoring and webhook paths',
            icon: Activity,
            tint: 'rgba(56,189,248,0.14)',
            color: 'var(--neon-cyan)',
          },
        ].map(item => (
          <Link
            key={item.to}
            to={item.to}
            className="glass rounded-xl p-4 flex items-start gap-3 hover-lift transition-all"
            style={{ border: '1px solid var(--border)' }}
          >
            <div className="p-2 rounded-lg" style={{ background: item.tint }}>
              <item.icon size={16} style={{ color: item.color }} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>{item.title}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{item.desc}</div>
            </div>
          </Link>
        ))}
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 p-1 rounded-xl overflow-x-auto" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setTab(tab.id)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap"
            style={{
              background: activeTab === tab.id ? 'var(--bg-card)' : 'transparent',
              color:      activeTab === tab.id ? 'var(--text-heading)' : 'var(--text-muted)',
              boxShadow:  activeTab === tab.id ? 'var(--glass-shadow)' : 'none',
              border:     activeTab === tab.id ? '1px solid var(--border)' : '1px solid transparent',
            }}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview'  && <OverviewTab onNavigate={setTab} />}
      {activeTab === 'members'   && <MembersTab />}
      {activeTab === 'activity'  && <ActivityTab />}
    </div>
  )
}
