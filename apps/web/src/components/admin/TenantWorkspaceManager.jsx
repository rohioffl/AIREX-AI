import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Building2,
  CheckCircle,
  Edit,
  Globe,
  Plus,
  RefreshCcw,
  Search,
  Server,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'

import ModalShell from '../common/ModalShell'
import { useAuth } from '../../context/AuthContext'
import { useToasts } from '../../context/ToastContext'
import {
  createProjectMonitorBinding,
  createIntegration,
  createOrganization,
  createOrganizationTenant,
  createProject,
  createTenant,
  deleteIntegration,
  deleteProjectMonitorBinding,
  deleteProject,
  deleteTenant,
  fetchExternalMonitors,
  fetchIntegrationTypes,
  fetchProjectMonitorBindings,
  fetchTenantDetail,
  reloadTenants,
  syncIntegrationMonitors,
  testIntegration,
  updateTenant,
} from '../../services/api'
import { useTenantWorkspace } from '../../hooks/useTenantWorkspace'
import { extractErrorMessage } from '../../utils/errorHandler'
import { normalizeRole } from '../../utils/accessControl'

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

const AWS_AUTH_METHODS = [
  { value: 'role_assume', label: 'Cross-Account Role (Recommended)', desc: 'Assume role using account ID + role name' },
  { value: 'role_arn',    label: 'Direct Role ARN',                  desc: 'Provide a full AWS IAM role ARN' },
  { value: 'access_keys', label: 'Access Key + Secret',              desc: 'Static credentials stored in DB' },
  { value: 'creds_file',  label: 'Credentials File Path',            desc: 'Path to credentials file on server' },
  { value: 'instance',    label: 'EC2 Instance Role',                desc: 'Use instance profile / metadata role' },
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

function DetailField({ label, value, mono = false, tone = 'var(--text-heading)' }) {
  return (
    <div className="rounded-xl p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ fontSize: 13, color: tone, marginTop: 5, fontFamily: mono ? 'var(--font-mono)' : 'inherit', wordBreak: 'break-word' }}>
        {value || 'Not configured'}
      </div>
    </div>
  )
}

export default function TenantWorkspaceManager({ mode = 'workspace', initialOrganizationId = null }) {
  const { addToast } = useToasts()
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [showOnboard, setShowOnboard] = useState(false)
  const [editingTenant, setEditingTenant] = useState(null)
  const [deletingTenant, setDeletingTenant] = useState(null)
  const [showCreateOrganization, setShowCreateOrganization] = useState(false)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [showCreateIntegration, setShowCreateIntegration] = useState(false)
  const [externalMonitorsByIntegration, setExternalMonitorsByIntegration] = useState({})
  const [loadingMonitorsByIntegration, setLoadingMonitorsByIntegration] = useState({})
  const [bindingsByProject, setBindingsByProject] = useState({})
  const [selectedProjectByMonitor, setSelectedProjectByMonitor] = useState({})
  const [bindingBusyKey, setBindingBusyKey] = useState(null)

  const isPlatformInventoryMode = mode === 'platform'
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
    loadDetails: !isPlatformInventoryMode,
    initialOrganizationId,
  })

  const filtered = useMemo(() => {
    if (!search) return tenants
    const q = search.toLowerCase()
    return tenants.filter(t => t.name?.toLowerCase().includes(q) || t.display_name?.toLowerCase().includes(q) || t.cloud?.toLowerCase().includes(q))
  }, [tenants, search])

  const pageIntro = useMemo(() => {
    if (mode === 'organizations') {
      return {
        title: 'Organizations',
        subtitle: 'Manage customer organizations and onboard tenants into the correct workspace.',
      }
    }
    if (mode === 'integrations') {
      return {
        title: 'Integrations',
        subtitle: 'Configure tenant-owned monitoring integrations, webhook endpoints, and sync status.',
      }
    }
    if (mode === 'platform') {
      return {
        title: 'Tenant Workspaces',
        subtitle: 'Manage tenant inventory, onboarding, and organization placement without loading tenant-owned projects or integrations.',
      }
    }
    return {
      title: 'Tenant Workspaces',
      subtitle: 'Manage tenants, projects, and workspace-level SaaS configuration.',
    }
  }, [mode])

  const canManageOrganizations = normalizeRole(user?.role) === 'platform_admin'

  const refreshProjectBindings = useCallback(async () => {
    if (!selectedTenant || projects.length === 0) {
      setBindingsByProject({})
      return
    }
    try {
      const rows = await Promise.all(
        projects.map(async (project) => ({
          projectId: project.id,
          bindings: await fetchProjectMonitorBindings(project.id),
        }))
      )
      const nextBindings = {}
      rows.forEach(({ projectId, bindings }) => {
        nextBindings[projectId] = Array.isArray(bindings) ? bindings : []
      })
      setBindingsByProject(nextBindings)
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to load project monitor bindings', 'error')
    }
  }, [projects, selectedTenant, toast])

  useEffect(() => {
    if (!selectedTenantId) {
      setExternalMonitorsByIntegration({})
      setBindingsByProject({})
      return
    }
    setExternalMonitorsByIntegration({})
    setSelectedProjectByMonitor({})
    refreshProjectBindings()
  }, [refreshProjectBindings, selectedTenantId])

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

  const handleLoadExternalMonitors = async (integrationId) => {
    setLoadingMonitorsByIntegration((prev) => ({ ...prev, [integrationId]: true }))
    try {
      const monitors = await fetchExternalMonitors(integrationId)
      setExternalMonitorsByIntegration((prev) => ({
        ...prev,
        [integrationId]: Array.isArray(monitors) ? monitors : [],
      }))
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to load external monitors', 'error')
    } finally {
      setLoadingMonitorsByIntegration((prev) => ({ ...prev, [integrationId]: false }))
    }
  }

  const handleCreateBinding = async (projectId, monitorId) => {
    if (!projectId) {
      toast('Select a project first', 'error')
      return
    }
    const busyKey = `${projectId}:${monitorId}`
    setBindingBusyKey(busyKey)
    try {
      await createProjectMonitorBinding(projectId, {
        external_monitor_id: monitorId,
        enabled: true,
      })
      toast('Monitor binding created')
      await refreshProjectBindings()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to create monitor binding', 'error')
    } finally {
      setBindingBusyKey(null)
    }
  }

  const handleDeleteBinding = async (bindingId) => {
    setBindingBusyKey(bindingId)
    try {
      await deleteProjectMonitorBinding(bindingId)
      toast('Monitor binding removed')
      await refreshProjectBindings()
    } catch (err) {
      toast(extractErrorMessage(err) || 'Failed to remove monitor binding', 'error')
    } finally {
      setBindingBusyKey(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="glass rounded-xl p-5">
        <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>{pageIntro.title}</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>{pageIntro.subtitle}</div>
      </div>

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
          {canManageOrganizations && (
            <button onClick={() => setShowCreateOrganization(true)} className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
              <ShieldCheck size={14} /> Add Organization
            </button>
          )}
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
                {!isPlatformInventoryMode && (
                  <div className="flex items-center gap-1">
                    <button onClick={(event) => { event.stopPropagation(); openEdit(t) }} className="p-2 rounded-lg" style={{ background: 'transparent' }} title="Edit">
                      <Edit size={14} style={{ color: 'var(--text-muted)' }} />
                    </button>
                    <button onClick={(event) => { event.stopPropagation(); setDeletingTenant(t) }} className="p-2 rounded-lg" style={{ background: 'transparent' }} title="Delete">
                      <Trash2 size={14} style={{ color: 'var(--color-accent-amber)' }} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {isPlatformInventoryMode && (
        <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
          <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
            <SectionHeader
              title={selectedTenant ? `Tenant Profile · ${selectedTenant.display_name}` : 'Tenant Profile'}
            />

            {!selectedTenant ? (
              <div className="rounded-xl p-5" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Select a tenant</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
                  Pick a tenant from the inventory above to review its SaaS profile, ownership, cloud placement, and onboarding readiness.
                </div>
              </div>
            ) : (
              <>
                <div className="rounded-2xl p-5" style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.12), rgba(34,211,238,0.08))', border: '1px solid rgba(99,102,241,0.18)' }}>
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-heading)' }}>{selectedTenant.display_name}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
                        SaaS workspace record for onboarding, ownership, and operational routing.
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <CloudBadge cloud={selectedTenant.cloud} />
                      <CredBadge status={selectedTenant.credential_status} />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <DetailField label="Tenant Slug" value={selectedTenant.name} mono />
                  <DetailField label="Organization" value={selectedTenant.organization_name || organizations.find((org) => org.id === activeOrganizationId)?.name} />
                  <DetailField label="Escalation Email" value={selectedTenant.escalation_email} />
                  <DetailField label="Slack Channel" value={selectedTenant.slack_channel} mono />
                  <DetailField label="SSH User" value={selectedTenant.ssh_user} mono />
                  <DetailField label="Servers" value={String(selectedTenant.server_count ?? 0)} tone="var(--neon-cyan)" mono />
                </div>
              </>
            )}
          </div>

          <div className="glass rounded-xl p-5 space-y-4" style={{ border: '1px solid var(--border)' }}>
            <SectionHeader title="SaaS Admin Guardrails" />
            <div className="space-y-3">
              {[
                {
                  title: 'Tenant onboarding belongs here',
                  body: 'Provision new customer environments, attach them to the right organization, and maintain customer-facing workspace metadata from this page.',
                },
                {
                  title: 'Tenant internals stay scoped',
                  body: 'Project catalogs, tenant integrations, and monitor bindings remain in organization or tenant admin surfaces so platform admins do not operate inside shared tenant context by accident.',
                },
                {
                  title: 'Profiles are view-only here',
                  body: 'Platform admins can review tenant metadata from this inventory view, while tenant profile changes remain in the scoped admin workflows.',
                },
              ].map((item) => (
                <div key={item.title} className="rounded-xl p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)' }}>{item.title}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>{item.body}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!isPlatformInventoryMode && (
      <div className={`grid grid-cols-1 ${mode === 'organizations' ? 'xl:grid-cols-1' : 'xl:grid-cols-2'} gap-6`}>
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

        {mode !== 'organizations' && (
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
                      {integration.webhook_path && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                          Webhook
                          <span style={{ display: 'block', fontFamily: 'var(--font-mono)', color: 'var(--text-heading)', marginTop: 2 }}>
                            {integration.webhook_path}
                          </span>
                        </div>
                      )}
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
                    <button onClick={() => handleLoadExternalMonitors(integration.id)} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'rgba(167,139,250,0.10)', color: 'var(--neon-purple)', border: '1px solid rgba(167,139,250,0.2)' }}>
                      {loadingMonitorsByIntegration[integration.id] ? 'Loading…' : 'Load External Monitors'}
                    </button>
                    <button onClick={() => handleDeleteIntegration(integration)} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'rgba(251,191,36,0.08)', color: 'var(--color-accent-amber)', border: '1px solid rgba(251,191,36,0.18)' }}>
                      Disable
                    </button>
                  </div>
                  {Array.isArray(externalMonitorsByIntegration[integration.id]) && externalMonitorsByIntegration[integration.id].length > 0 && (
                    <div className="mt-3 space-y-2">
                      {externalMonitorsByIntegration[integration.id].map((monitor) => {
                        const monitorBindings = projects.flatMap((project) => {
                          const binding = (bindingsByProject[project.id] || []).find(
                            (row) => row.external_monitor_id === monitor.id
                          )
                          if (!binding) return []
                          return [{ ...binding, projectName: project.name }]
                        })

                        const selectedProjectId = selectedProjectByMonitor[monitor.id] || ''
                        const selectedProjectAlreadyBound = selectedProjectId
                          ? (bindingsByProject[selectedProjectId] || []).some(
                              (row) => row.external_monitor_id === monitor.id
                            )
                          : false

                        return (
                          <div key={monitor.id} className="rounded-lg p-3" style={{ border: '1px solid var(--border)' }}>
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)' }}>{monitor.external_name}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                  <span style={{ fontFamily: 'var(--font-mono)' }}>{monitor.external_monitor_id}</span>
                                  <span> · {monitor.monitor_type}</span>
                                </div>
                              </div>
                              <span style={{ fontSize: 11, color: monitor.enabled ? 'var(--neon-green)' : 'var(--text-muted)' }}>
                                {monitor.status || 'synced'}
                              </span>
                            </div>
                            <div className="mt-2 flex items-center gap-2 flex-wrap">
                              <select
                                aria-label={`Bind ${monitor.external_name} to project`}
                                value={selectedProjectId}
                                onChange={(event) => setSelectedProjectByMonitor((prev) => ({ ...prev, [monitor.id]: event.target.value }))}
                                style={{ ...inputCls, maxWidth: 220, padding: '6px 10px', fontSize: 12 }}
                              >
                                <option value="">Select project to bind</option>
                                {projects.map((project) => (
                                  <option key={project.id} value={project.id}>
                                    {project.name}
                                  </option>
                                ))}
                              </select>
                              <button
                                onClick={() => handleCreateBinding(selectedProjectId, monitor.id)}
                                disabled={!selectedProjectId || selectedProjectAlreadyBound || bindingBusyKey === `${selectedProjectId}:${monitor.id}`}
                                className="px-3 py-1.5 rounded-lg text-xs disabled:opacity-60"
                                style={{ background: 'rgba(52,211,153,0.08)', color: 'var(--neon-green)', border: '1px solid rgba(52,211,153,0.18)' }}
                              >
                                Bind to project
                              </button>
                            </div>
                            {monitorBindings.length > 0 ? (
                              <div className="mt-2 flex items-center gap-2 flex-wrap">
                                {monitorBindings.map((binding) => (
                                  <button
                                    key={binding.id}
                                    onClick={() => handleDeleteBinding(binding.id)}
                                    disabled={bindingBusyKey === binding.id}
                                    className="px-2.5 py-1 rounded-lg text-xs disabled:opacity-60"
                                    style={{ background: 'rgba(251,191,36,0.08)', color: 'var(--color-accent-amber)', border: '1px solid rgba(251,191,36,0.18)' }}
                                  >
                                    {bindingBusyKey === binding.id ? 'Removing…' : `Unbind ${binding.projectName}`}
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                                No project bindings yet
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        )}
      </div>
      )}

      {showOnboard && <TenantOnboardModal organizationId={activeOrganizationId} onClose={() => setShowOnboard(false)} onSaved={() => { setShowOnboard(false); reloadWorkspace() }} />}
      {editingTenant && <TenantEditDrawer tenant={editingTenant} onClose={() => setEditingTenant(null)} onSaved={() => { setEditingTenant(null); reloadWorkspace() }} />}
      {canManageOrganizations && showCreateOrganization && <OrganizationCreateModal onClose={() => setShowCreateOrganization(false)} onSaved={() => { setShowCreateOrganization(false); reloadWorkspace() }} />}
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
