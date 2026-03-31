import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Zap, RefreshCw, Trash2, AlertCircle, CheckCircle, Clock, Plug, List, RotateCcw, Copy, X, KeyRound } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { isPlatformAdmin } from '../../utils/accessControl'
import {
  fetchIntegrationTypes,
  fetchIntegrations,
  fetchProjects,
  fetchCloudAccounts,
  deleteIntegration,
  testIntegration,
  syncIntegrationMonitors,
  fetchWebhookEvents,
  replayWebhookEvent,
  rotateIntegrationSecret,
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

const EVENT_STATUS_COLOR = {
  processed: 'var(--neon-green)',
  error: '#ef4444',
  duplicate: 'var(--text-muted)',
  queued: 'var(--neon-cyan)',
}

const ACTIVE_INTEGRATION_TYPE_KEYS = new Set(['site24x7'])

function WebhookEventsPanel({ integration, onClose }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [replayingId, setReplayingId] = useState(null)
  const [rotatingSecret, setRotatingSecret] = useState(false)
  const [newToken, setNewToken] = useState(null)
  const [copied, setCopied] = useState(false)

  const webhookUrl = integration.webhook_path
    ? `${window.location.origin}${integration.webhook_path}`
    : ''

  const loadEvents = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchWebhookEvents(integration.id, 50)
      setEvents(data || [])
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [integration.id])

  useEffect(() => {
    loadEvents()
  }, [loadEvents])

  async function handleCopyUrl() {
    try {
      await navigator.clipboard.writeText(webhookUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback: select text
    }
  }

  async function handleReplay(integrationId, eventId) {
    setReplayingId(eventId)
    try {
      await replayWebhookEvent(integrationId, eventId)
      loadEvents()
    } catch {
      // ignore
    } finally {
      setReplayingId(null)
    }
  }

  async function handleRotateSecret() {
    if (!window.confirm('Rotate webhook secret? The old token will stop working immediately.')) return
    setRotatingSecret(true)
    try {
      const res = await rotateIntegrationSecret(integration.id)
      setNewToken(res.webhook_token)
    } catch {
      // ignore
    } finally {
      setRotatingSecret(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'flex-end',
      }}
    >
      {/* Overlay */}
      <div
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="glass flex flex-col"
        style={{
          position: 'relative',
          width: 520,
          maxWidth: '100vw',
          height: '100vh',
          borderLeft: '1px solid var(--border)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between"
          style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)' }}>
              Webhook Events
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {integration.name}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Webhook URL copy block */}
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Webhook URL
          </div>
          <div
            className="flex items-center gap-2"
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '8px 12px',
            }}
          >
            <code style={{ fontSize: 11, color: 'var(--neon-cyan)', flex: 1, wordBreak: 'break-all' }}>
              {webhookUrl}
            </code>
            <button
              onClick={handleCopyUrl}
              title="Copy URL"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--neon-green)' : 'var(--text-muted)', flexShrink: 0, padding: 2 }}
            >
              <Copy size={13} />
            </button>
          </div>

          {/* Rotate secret */}
          <div className="flex items-center justify-between mt-3">
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {newToken
                ? <span style={{ color: 'var(--neon-green)' }}>New token: <code style={{ fontSize: 11 }}>{newToken}</code></span>
                : 'Webhook token stored securely.'}
            </span>
            <button
              onClick={handleRotateSecret}
              disabled={rotatingSecret}
              className="flex items-center gap-1.5"
              style={{ fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 6, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', cursor: 'pointer' }}
            >
              {rotatingSecret ? <RefreshCw size={11} className="animate-spin" /> : <KeyRound size={11} />}
              Rotate Token
            </button>
          </div>
        </div>

        {/* Events list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px 20px' }}>
          <div className="flex items-center justify-between" style={{ padding: '12px 0 8px' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
              Recent Events ({events.length})
            </span>
            <button
              onClick={loadEvents}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
            >
              <RefreshCw size={12} />
            </button>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-10">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          )}

          {!loading && events.length === 0 && (
            <div className="text-center py-10">
              <List size={20} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No webhook events recorded yet.</p>
            </div>
          )}

          {!loading && events.map((ev) => (
            <div
              key={ev.id}
              className="flex items-start gap-3"
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                marginBottom: 8,
                background: ev.is_replay ? 'rgba(99,102,241,0.05)' : 'transparent',
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: '1px 6px',
                      borderRadius: 10,
                      background: `${EVENT_STATUS_COLOR[ev.status] || 'var(--text-muted)'}22`,
                      color: EVENT_STATUS_COLOR[ev.status] || 'var(--text-muted)',
                      border: `1px solid ${EVENT_STATUS_COLOR[ev.status] || 'var(--text-muted)'}44`,
                    }}
                  >
                    {ev.status}
                  </span>
                  {ev.event_type && (
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{ev.event_type}</span>
                  )}
                  {ev.is_replay && (
                    <span style={{ fontSize: 10, color: 'var(--neon-indigo)', fontWeight: 600 }}>REPLAY</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  {new Date(ev.received_at).toLocaleString()}
                  {ev.incident_id && (
                    <span style={{ marginLeft: 8, color: 'var(--neon-cyan)' }}>
                      → incident
                    </span>
                  )}
                </div>
                {ev.dedup_key && (
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'monospace' }}>
                    {ev.dedup_key.length > 40 ? ev.dedup_key.slice(0, 40) + '…' : ev.dedup_key}
                  </div>
                )}
              </div>
              <button
                onClick={() => handleReplay(integration.id, ev.id)}
                disabled={replayingId === ev.id}
                title="Replay event"
                style={{ padding: '5px 8px', borderRadius: 6, background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--neon-indigo)', cursor: 'pointer', flexShrink: 0 }}
              >
                {replayingId === ev.id
                  ? <RefreshCw size={11} className="animate-spin" />
                  : <RotateCcw size={11} />}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function IntegrationCard({
  integrationType,
  integration,
  onAdd,
  onEdit,
  onRefresh,
  onShowEvents,
  comingSoon = false,
  highlighted = false,
}) {
  const [actionLoading, setActionLoading] = useState(null)
  const statusMeta = integration ? (STATUS_META[integration.status] || STATUS_META.unknown) : null
  const StatusIcon = statusMeta?.icon
  const supportsWebhook = integrationType.supports_webhook

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
      id={`integration-card-${integrationType.key}`}
      className="glass rounded-xl p-5 flex flex-col gap-4"
      style={{
        border: highlighted
          ? '1px solid rgba(34,211,238,0.55)'
          : integration
            ? '1px solid rgba(34,211,238,0.2)'
            : '1px solid var(--border)',
        position: 'relative',
        boxShadow: highlighted ? '0 0 0 1px rgba(34,211,238,0.18), 0 0 32px rgba(34,211,238,0.12)' : 'none',
        scrollMarginTop: 96,
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
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', lineHeight: 1.2 }}>
            {integrationType.display_name}
          </div>
          {integration && (
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              {integration.name}
            </div>
          )}
          {integration?.cloud_account_display_name && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              {integration.cloud_account_display_name}
              {integration.cloud_account_external_id
                ? ` · ${integration.cloud_account_external_id}`
                : ''}
            </div>
          )}
          <div className="flex items-center gap-2 mt-2" style={{ flexWrap: 'wrap' }}>
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

      {/* Alert source stats */}
      {integration && (
        <div className="flex items-center gap-3 flex-wrap" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ fontFamily: 'var(--font-mono)', color: integration.recent_alert_count > 0 ? 'var(--neon-cyan)' : 'var(--text-muted)', fontWeight: 600 }}>
            {integration.recent_alert_count} alerts (7d)
          </span>
          {integration.last_alert_at && (
            <span>Last alert {new Date(integration.last_alert_at).toLocaleString()}</span>
          )}
          {!integration.last_alert_at && (
            <span>No alerts recorded</span>
          )}
        </div>
      )}

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
            {supportsWebhook && (
              <button
                onClick={() => onShowEvents(integration)}
                title="Webhook events"
                style={{ padding: '6px 8px', borderRadius: 8, background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--neon-purple)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              >
                <List size={13} />
              </button>
            )}
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
          comingSoon ? (
            <div
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-semibold"
              style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.28)', color: '#f59e0b' }}
            >
              <AlertCircle size={13} />
              Coming Soon
            </div>
          ) : (
            <button
              onClick={() => onAdd(integrationType)}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-semibold"
              style={{ background: `${categoryColor}22`, border: `1px solid ${categoryColor}44`, color: categoryColor, cursor: 'pointer' }}
            >
              <Plus size={13} />
              Add
            </button>
          )
        )}
      </div>
    </div>
  )
}

export default function IntegrationsAdminPage({
  embedded = false,
  tenantId: propTenantId = null,
  launchIntegrationKey = null,
  launchSignal = 0,
  onDataChange = null,
}) {
  const auth = useAuth()
  const [searchParams] = useSearchParams()
  const { activeTenantId: authTenantId, projects: ctxProjects } = auth
  const activeTenantId = propTenantId || authTenantId
  const launchIntegrationQueryKey = searchParams.get('integration')
  const launchBindingId = searchParams.get('binding')
  const backTarget = isPlatformAdmin(auth) ? '/admin' : '/admin/workspaces'
  const backLabel = isPlatformAdmin(auth) ? 'Back to Platform Admin' : 'Back to Workspaces'
  const [integrationTypes, setIntegrationTypes] = useState([])
  const [integrations, setIntegrations] = useState([])
  const [projects, setProjects] = useState(ctxProjects || [])
  const [cloudAccounts, setCloudAccounts] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [wizardType, setWizardType] = useState(null)
  const [wizardIntegration, setWizardIntegration] = useState(null)
  const [eventsIntegration, setEventsIntegration] = useState(null)
  const [highlightedIntegrationKey, setHighlightedIntegrationKey] = useState(null)

  const publishData = useCallback((types, configured) => {
    onDataChange?.({
      availableCount: (types || []).length,
      configuredCount: (configured || []).length,
      configured: configured || [],
      types: types || [],
    })
  }, [onDataChange])

  const loadData = useCallback(async () => {
    if (!activeTenantId) return
    try {
      const [types, configured, projs, accounts] = await Promise.all([
        fetchIntegrationTypes(),
        fetchIntegrations(activeTenantId),
        fetchProjects(activeTenantId),
        fetchCloudAccounts(null, activeTenantId),
      ])
      const sortedTypes = (types || [])
        .slice()
        .sort((left, right) => {
          const leftActive = ACTIVE_INTEGRATION_TYPE_KEYS.has(left.key)
          const rightActive = ACTIVE_INTEGRATION_TYPE_KEYS.has(right.key)
          if (leftActive !== rightActive) return leftActive ? -1 : 1
          return left.display_name.localeCompare(right.display_name)
        })
      setIntegrationTypes(sortedTypes)
      setIntegrations(configured || [])
      setProjects(projs || [])
      setCloudAccounts(accounts || [])
      publishData(sortedTypes, configured || [])
    } catch (err) {
      console.error('Failed to load integrations:', err)
    } finally {
      setIsLoading(false)
    }
  }, [activeTenantId, publishData])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    const requestedIntegrationKey = launchIntegrationKey || launchIntegrationQueryKey
    if (!requestedIntegrationKey || integrationTypes.length === 0) return
    const integrationType = integrationTypes.find((item) => item.key === requestedIntegrationKey)
    if (!integrationType) return
    if (ACTIVE_INTEGRATION_TYPE_KEYS.has(integrationType.key)) {
      setWizardType(integrationType)
      setWizardIntegration(null)
      return
    }

    setHighlightedIntegrationKey(integrationType.key)
    requestAnimationFrame(() => {
      document.getElementById(`integration-card-${integrationType.key}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    })
  }, [integrationTypes, launchIntegrationKey, launchIntegrationQueryKey, launchSignal])

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
  const available = integrationTypes.filter(
    (t) => !integrationByTypeId[t.id] && ACTIVE_INTEGRATION_TYPE_KEYS.has(t.key)
  )
  const comingSoon = integrationTypes.filter(
    (t) => !integrationByTypeId[t.id] && !ACTIVE_INTEGRATION_TYPE_KEYS.has(t.key)
  )

  return (
    <div className="space-y-6 animate-fade-in">
      {!embedded && (
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
            to={backTarget}
            className="px-4 py-2 rounded-lg text-sm font-semibold"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            {backLabel}
          </Link>
        </div>
      )}

      {!activeTenantId && (
        <div className="glass rounded-xl p-6 text-center" style={{ border: '1px dashed var(--border)' }}>
          <AlertCircle size={20} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            No active workspace. Select a workspace to manage integrations.
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
                    onShowEvents={setEventsIntegration}
                    highlighted={highlightedIntegrationKey === t.key}
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
                    onShowEvents={setEventsIntegration}
                    highlighted={highlightedIntegrationKey === t.key}
                  />
                ))}
              </div>
            </section>
          )}

          {comingSoon.length > 0 && (
            <section>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Coming Soon ({comingSoon.length})
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
                {comingSoon.map((t) => (
                  <IntegrationCard
                    key={t.id}
                    integrationType={t}
                    integration={null}
                    comingSoon
                    onAdd={handleAdd}
                    onEdit={handleEdit}
                    onRefresh={loadData}
                    onShowEvents={setEventsIntegration}
                    highlighted={highlightedIntegrationKey === t.key}
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
          cloudAccounts={cloudAccounts}
          defaultCloudAccountBindingId={launchBindingId}
          onClose={closeWizard}
          onSaved={loadData}
        />
      )}

      {eventsIntegration && (
        <WebhookEventsPanel
          integration={eventsIntegration}
          onClose={() => setEventsIntegration(null)}
        />
      )}
    </div>
  )
}
