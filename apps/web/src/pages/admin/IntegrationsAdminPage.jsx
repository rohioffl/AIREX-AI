import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Zap, RefreshCw, Trash2, AlertCircle, CheckCircle, Clock, Plug } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import {
  fetchIntegrationTypes,
  fetchIntegrations,
  fetchProjects,
  deleteIntegration,
  testIntegration,
  syncIntegrationMonitors,
} from '../../services/api'
import IntegrationConfigWizard from '../../components/admin/IntegrationConfigWizard'

const CATEGORY_COLORS = {
  monitoring: 'var(--neon-cyan)',
  apm: 'var(--neon-indigo)',
  logging: 'var(--neon-purple)',
  alerting: 'var(--neon-green)',
}

const STATUS_META = {
  verified: { color: 'var(--neon-green)', icon: CheckCircle, label: 'Verified' },
  configured: { color: 'var(--neon-cyan)', icon: Clock, label: 'Configured' },
  error: { color: '#ef4444', icon: AlertCircle, label: 'Error' },
  unknown: { color: 'var(--text-muted)', icon: Clock, label: 'Unknown' },
}

function DeliveryBadge({ label, active }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 7px',
        borderRadius: 20,
        border: '1px solid',
        borderColor: active ? 'var(--neon-cyan)' : 'var(--border)',
        color: active ? 'var(--neon-cyan)' : 'var(--text-muted)',
        background: active ? 'rgba(34,211,238,0.1)' : 'transparent',
      }}
    >
      {label}
    </span>
  )
}

function IntegrationCard({ integrationType, integration, onAdd, onEdit, onRefresh }) {
  const [actionLoading, setActionLoading] = useState(null)
  const statusMeta = integration ? (STATUS_META[integration.status] || STATUS_META.unknown) : null
  const StatusIcon = statusMeta?.icon

  async function handleTest() {
    setActionLoading('test')
    try {
      await testIntegration(integration.id)
      onRefresh()
    } catch {
      // error shown via status update on refresh
    } finally {
      setActionLoading(null)
    }
  }

  async function handleSync() {
    setActionLoading('sync')
    try {
      await syncIntegrationMonitors(integration.id)
      onRefresh()
    } catch {
      // ignore
    } finally {
      setActionLoading(null)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Remove integration "${integration.name}"?`)) return
    setActionLoading('delete')
    try {
      await deleteIntegration(integration.id)
      onRefresh()
    } catch {
      // ignore
    } finally {
      setActionLoading(null)
    }
  }

  const categoryColor = CATEGORY_COLORS[integrationType.category] || 'var(--neon-cyan)'

  return (
    <div
      className="glass rounded-xl p-5 flex flex-col gap-4"
      style={{
        border: integration ? '1px solid rgba(34,211,238,0.2)' : '1px solid var(--border)',
        position: 'relative',
      }}
    >
      {/* Status dot for configured integrations */}
      {statusMeta && (
        <div
          style={{
            position: 'absolute',
            top: 14,
            right: 14,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 11,
            color: statusMeta.color,
            fontWeight: 600,
          }}
        >
          <StatusIcon size={12} />
          {statusMeta.label}
        </div>
      )}

      {/* Provider identity */}
      <div className="flex items-start gap-3">
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: `${categoryColor}22`,
            border: `1px solid ${categoryColor}44`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <Plug size={18} style={{ color: categoryColor }} />
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', lineHeight: 1.2 }}>
            {integrationType.display_name}
          </div>
          {integration && (
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              {integration.name}
            </div>
          )}
          <div className="flex items-center gap-2 mt-2">
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: '2px 7px',
                borderRadius: 20,
                background: `${categoryColor}22`,
                color: categoryColor,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {integrationType.category}
            </span>
            <DeliveryBadge label="Webhook" active={integrationType.supports_webhook} />
            <DeliveryBadge label="Sync" active={integrationType.supports_sync} />
          </div>
        </div>
      </div>

      {/* Sync timestamps */}
      {integration?.last_tested_at && (
        <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Last tested {new Date(integration.last_tested_at).toLocaleString()}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto">
        {integration ? (
          <>
            <button
              onClick={() => onEdit(integrationType, integration)}
              className="flex-1 py-1.5 rounded-lg text-xs font-semibold"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer' }}
            >
              Edit
            </button>
            <button
              onClick={handleTest}
              disabled={actionLoading === 'test'}
              title="Test connection"
              style={{ padding: '6px 8px', borderRadius: 8, background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--neon-cyan)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              {actionLoading === 'test'
                ? <RefreshCw size={13} className="animate-spin" />
                : <Zap size={13} />}
            </button>
            {integrationType.supports_sync && (
              <button
                onClick={handleSync}
                disabled={actionLoading === 'sync'}
                title="Sync monitors"
                style={{ padding: '6px 8px', borderRadius: 8, background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--neon-indigo)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              >
                {actionLoading === 'sync'
                  ? <RefreshCw size={13} className="animate-spin" />
                  : <RefreshCw size={13} />}
              </button>
            )}
            <button
              onClick={handleDelete}
              disabled={actionLoading === 'delete'}
              title="Remove integration"
              style={{ padding: '6px 8px', borderRadius: 8, background: 'var(--bg-input)', border: '1px solid var(--border)', color: '#ef4444', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              <Trash2 size={13} />
            </button>
          </>
        ) : (
          <button
            onClick={() => onAdd(integrationType)}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-semibold"
            style={{ background: `${categoryColor}22`, border: `1px solid ${categoryColor}44`, color: categoryColor, cursor: 'pointer' }}
          >
            <Plus size={13} />
            Add
          </button>
        )}
      </div>
    </div>
  )
}

export default function IntegrationsAdminPage() {
  const { activeTenantId, projects: ctxProjects } = useAuth()
  const [integrationTypes, setIntegrationTypes] = useState([])
  const [integrations, setIntegrations] = useState([])
  const [projects, setProjects] = useState(ctxProjects || [])
  const [isLoading, setIsLoading] = useState(true)
  const [wizardType, setWizardType] = useState(null)
  const [wizardIntegration, setWizardIntegration] = useState(null)

  const loadData = useCallback(async () => {
    if (!activeTenantId) return
    try {
      const [types, configured, projs] = await Promise.all([
        fetchIntegrationTypes(),
        fetchIntegrations(activeTenantId),
        fetchProjects(activeTenantId),
      ])
      setIntegrationTypes(types || [])
      setIntegrations(configured || [])
      setProjects(projs || [])
    } catch (err) {
      console.error('Failed to load integrations:', err)
    } finally {
      setIsLoading(false)
    }
  }, [activeTenantId])

  useEffect(() => {
    loadData()
  }, [loadData])

  function handleAdd(integrationType) {
    setWizardType(integrationType)
    setWizardIntegration(null)
  }

  function handleEdit(integrationType, integration) {
    setWizardType(integrationType)
    setWizardIntegration(integration)
  }

  function closeWizard() {
    setWizardType(null)
    setWizardIntegration(null)
  }

  // Group integrations by integration_type_id for quick lookup
  const integrationByTypeId = {}
  for (const i of integrations) {
    integrationByTypeId[i.integration_type_id] = i
  }

  const configured = integrationTypes.filter((t) => integrationByTypeId[t.id])
  const available = integrationTypes.filter((t) => !integrationByTypeId[t.id])

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            Monitoring Integrations
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Connect monitoring providers to route alerts into incident workflows.
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

      {!activeTenantId && (
        <div className="glass rounded-xl p-6 text-center" style={{ border: '1px dashed var(--border)' }}>
          <AlertCircle size={20} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            No active tenant. Select a tenant to manage integrations.
          </p>
        </div>
      )}

      {activeTenantId && isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
        </div>
      )}

      {activeTenantId && !isLoading && (
        <>
          {/* Configured integrations */}
          {configured.length > 0 && (
            <section>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Configured ({configured.length})
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
                {configured.map((t) => (
                  <IntegrationCard
                    key={t.id}
                    integrationType={t}
                    integration={integrationByTypeId[t.id]}
                    onAdd={handleAdd}
                    onEdit={handleEdit}
                    onRefresh={loadData}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Available catalog */}
          {available.length > 0 && (
            <section>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Available ({available.length})
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
                {available.map((t) => (
                  <IntegrationCard
                    key={t.id}
                    integrationType={t}
                    integration={null}
                    onAdd={handleAdd}
                    onEdit={handleEdit}
                    onRefresh={loadData}
                  />
                ))}
              </div>
            </section>
          )}

          {integrationTypes.length === 0 && (
            <div className="glass rounded-xl p-12 text-center">
              <Plug size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
              <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No integration types available.</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                Run the seed migration to populate the integration catalog.
              </p>
            </div>
          )}
        </>
      )}

      {wizardType && (
        <IntegrationConfigWizard
          integrationType={wizardType}
          integration={wizardIntegration}
          tenantId={activeTenantId}
          projects={projects}
          onClose={closeWizard}
          onSaved={loadData}
        />
      )}
    </div>
  )
}
