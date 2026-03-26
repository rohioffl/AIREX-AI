import { useMemo, useState, useEffect } from 'react'
import { AlertTriangle, RefreshCcw, TrendingUp, Bell, Activity, CheckCircle, Building2, Layers } from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import { fetchMetrics, fetchOrganizationAnalytics } from '../services/api'
import { useAuth } from '../context/AuthContext'
import ConnectionBanner from '../components/common/ConnectionBanner'
import MetricCard from '../components/common/MetricCard'
import SystemGraph from '../components/common/SystemGraph'
import AlertHistoryWidget from '../components/common/AlertHistoryWidget'
import AlertRow from '../components/alert/AlertRow'
import { formatTimestamp, formatDuration } from '../utils/formatters'

const ACTIVE_STATES = [
  'RECEIVED',
  'INVESTIGATING',
  'RECOMMENDATION_READY',
  'AWAITING_APPROVAL',
  'EXECUTING',
  'VERIFYING',
]

const TERMINAL_STATES = ['RESOLVED', 'FAILED_EXECUTION', 'FAILED_VERIFICATION', 'REJECTED']

export default function DashboardPage() {
  const { incidents, loading, error, connected, reconnecting, reload } = useIncidents()
  const { activeTenant, activeOrganization, user, organizationMemberships } = useAuth()
  const [graphType, setGraphType] = useState('area')
  const [metrics, setMetrics] = useState(null)
  const [_metricsLoading, setMetricsLoading] = useState(true)
  const [orgScope, setOrgScope] = useState('tenant')
  const [orgAnalytics, setOrgAnalytics] = useState(null)
  const [orgAnalyticsLoading, setOrgAnalyticsLoading] = useState(false)

  const isOrgAdmin = useMemo(() => {
    if (!activeOrganization) return false
    const role = user?.role?.toLowerCase()
    if (role === 'admin' || role === 'platform_admin') return true
    return organizationMemberships?.some(
      (m) => String(m.organization_id) === String(activeOrganization.id) && m.role === 'admin'
    ) ?? false
  }, [activeOrganization, user, organizationMemberships])

  useEffect(() => {
    loadMetrics()
    const interval = setInterval(loadMetrics, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (orgScope === 'org' && activeOrganization?.id) {
      loadOrgAnalytics()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgScope, activeOrganization?.id])

  const loadMetrics = async () => {
    try {
      setMetricsLoading(true)
      const data = await fetchMetrics()
      setMetrics(data)
    } catch (err) {
      console.error('Failed to load metrics:', err)
    } finally {
      setMetricsLoading(false)
    }
  }

  const loadOrgAnalytics = async () => {
    if (!activeOrganization?.id) return
    try {
      setOrgAnalyticsLoading(true)
      const data = await fetchOrganizationAnalytics(activeOrganization.id)
      setOrgAnalytics(data)
    } catch (err) {
      console.error('Failed to load org analytics:', err)
    } finally {
      setOrgAnalyticsLoading(false)
    }
  }

  const latestFive = useMemo(() => {
    const sorted = [...incidents].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    return sorted.slice(0, 5)
  }, [incidents])

  const summary = useMemo(() => {
    const today = new Date().toDateString()
    let total = 0, pending = 0, actioned = 0, alertActions = 0

    incidents.forEach((i) => {
      if (ACTIVE_STATES.includes(i.state)) total += 1
      if (['AWAITING_APPROVAL', 'RECOMMENDATION_READY'].includes(i.state)) pending += 1
      if (['EXECUTING', 'VERIFYING'].includes(i.state)) actioned += 1
      if (TERMINAL_STATES.includes(i.state) && new Date(i.updated_at).toDateString() === today) alertActions += 1
    })

    // Prefer API metrics for totals
    if (metrics) {
      total = metrics.active_incidents || total
      alertActions = metrics.total_resolved_24h ?? alertActions
      actioned = metrics.acknowledged_count ?? actioned
      pending = metrics.pending_ack_count ?? pending
    }

    return {
      total,
      pending,
      actioned,
      alertActions,
      mttr: metrics?.mttr_seconds ? formatDuration(metrics.mttr_seconds) : null,
      aiConfidence: metrics?.ai_confidence_avg ? `${(metrics.ai_confidence_avg * 100).toFixed(1)}%` : null,
    }
  }, [incidents, metrics])

  const lastUpdated = latestFive[0]?.updated_at ? formatTimestamp(latestFive[0].updated_at) : '—'

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} onRetry={reload} />

      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <TrendingUp size={26} style={{ color: 'var(--neon-cyan)' }} />
            <span className="text-gradient-multi">Command Dashboard</span>
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: 'var(--color-accent-green)', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Snapshot of the five most recent alerts. Last updated {lastUpdated}.
          </p>
          {(activeTenant || activeOrganization) && (
            <div className="flex items-center flex-wrap gap-2 mt-2">
              {activeOrganization && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-md" style={{ fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.18)', color: 'var(--neon-indigo)' }}>
                  <Building2 size={11} />
                  {activeOrganization.name}
                </span>
              )}
              {activeOrganization && activeTenant && (
                <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>/</span>
              )}
              {activeTenant && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-md" style={{ fontSize: 11, fontWeight: 600, background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.18)', color: 'var(--neon-cyan)' }}>
                  <Layers size={11} />
                  {activeTenant.display_name || activeTenant.name}
                </span>
              )}
              {isOrgAdmin && activeOrganization && (
                <div className="flex rounded-md overflow-hidden ml-2" style={{ border: '1px solid var(--border)' }}>
                  {[
                    { key: 'tenant', label: 'This Tenant' },
                    { key: 'org', label: 'All Org Tenants' },
                  ].map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setOrgScope(key)}
                      className="px-2.5 py-0.5 text-xs font-semibold transition-all"
                      style={{
                        background: orgScope === key ? 'rgba(99,102,241,0.15)' : 'var(--bg-input)',
                        color: orgScope === key ? 'var(--neon-indigo)' : 'var(--text-muted)',
                        borderRight: key === 'tenant' ? '1px solid var(--border)' : 'none',
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        <button
          onClick={() => reload()}
          className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-all hover-lift hover:border-indigo-500/30 hover:text-indigo-400 hover:shadow-[0_0_15px_rgba(99,102,241,0.15)]"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          <RefreshCcw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { title: 'Total Alerts', value: String(summary.total), trend: 'Active incidents', trendType: 'neutral', icon: Bell },
          { title: 'Actioned', value: String(summary.actioned), trend: 'Executing or verifying', trendType: summary.actioned > 0 ? 'positive' : 'neutral', icon: Activity },
          { title: 'Pending', value: String(summary.pending), trend: 'Awaiting approval', trendType: summary.pending > 0 ? 'negative' : 'positive', icon: AlertTriangle, isCritical: summary.pending > 0 },
          { title: 'Alert Actions', value: String(summary.alertActions), trend: 'Resolved in last 24h', trendType: 'positive', icon: CheckCircle },
        ].map((props, i) => (
          <div key={i} className="animate-fade-in" style={{ animationDelay: `${i * 100}ms`, animationFillMode: 'both' }}>
            <MetricCard {...props} />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col gap-6">
          <SystemGraph incidents={incidents} type={graphType} />
          <AlertHistoryWidget days={7} />
        </div>
        <div className="glass glass-purple p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Telemetry</span>
            {orgScope === 'org' && (
              <span className="px-2 py-0.5 rounded-md text-xs font-semibold" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--neon-indigo)', border: '1px solid rgba(99,102,241,0.2)' }}>
                Org Scope
              </span>
            )}
          </div>
          <div className="flex-1 flex flex-col gap-3">
            {[
              {
                label: 'MTTR',
                value: metrics?.mttr_seconds
                  ? formatDuration(metrics.mttr_seconds)
                  : '—',
                color: 'var(--color-accent-green)'
              },
              {
                label: 'Avg Investigation',
                value: metrics?.avg_investigation_seconds
                  ? formatDuration(metrics.avg_investigation_seconds)
                  : '—',
                color: 'var(--neon-indigo)'
              },
              {
                label: 'AI Confidence',
                value: metrics?.ai_confidence_avg
                  ? `${Math.round(metrics.ai_confidence_avg * 100)}%`
                  : '—',
                color: 'var(--neon-purple)'
              },
              {
                label: 'Auto-resolved',
                value: metrics ? String(metrics.auto_resolved_count) : String(summary.alertActions),
                color: 'var(--neon-cyan)'
              },
            ].map((s) => (
              <div key={s.label} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.label}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: s.color }}>{s.value}</span>
              </div>
            ))}
            {orgScope === 'org' && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', paddingTop: 4 }}>
                  Org Analytics
                </div>
                {orgAnalyticsLoading ? (
                  <div className="h-12 rounded skeleton" />
                ) : orgAnalytics ? (
                  [
                    { label: 'Total Tenants', value: String(orgAnalytics.tenant_count ?? '—'), color: 'var(--neon-indigo)' },
                    { label: 'Active Tenants', value: String(orgAnalytics.active_tenant_count ?? '—'), color: 'var(--color-accent-green)' },
                    { label: 'Org Members', value: String(orgAnalytics.member_count ?? '—'), color: 'var(--neon-cyan)' },
                  ].map((s) => (
                    <div key={s.label} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.label}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: s.color }}>{s.value}</span>
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No org data available.</div>
                )}
              </>
            )}
          </div>
          <div className="flex gap-2 mt-auto">
            {['area', 'bar'].map((t) => (
              <button
                key={t}
                onClick={() => setGraphType(t)}
                className="flex-1 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-all"
                style={{
                  background: graphType === t ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                  color: graphType === t ? 'var(--neon-indigo)' : 'var(--text-muted)',
                  border: `1px solid ${graphType === t ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className="space-y-3">
          <div className="glass rounded-xl h-20 skeleton" />
          <div className="glass rounded-xl h-16 skeleton" />
          <div className="glass rounded-xl h-24 skeleton" />
        </div>
      )}

      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid var(--color-accent-red)', background: 'var(--glow-rose-subtle)', fontSize: 14, color: 'var(--color-accent-red)' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Latest 5 Alerts</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Synced {lastUpdated}</span>
          </div>
          {latestFive.length === 0 ? (
            <div className="glass rounded-xl py-14 text-center">
              <p style={{ fontSize: 15, color: 'var(--text-secondary)' }}>No alerts yet. Once incidents arrive they will appear here.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {latestFive.map((alert) => (
                <AlertRow key={alert.id} alert={alert} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// no-op placeholder to avoid empty file exports
