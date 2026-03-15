import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  HeartPulse, RefreshCw, AlertTriangle, CheckCircle2,
  XCircle, HelpCircle, Clock, Activity, ChevronDown,
  ChevronRight, ExternalLink, Zap, Server, Radar,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchHealthCheckDashboard, triggerHealthCheck, fetchMonitorInventory } from '../services/api'
import ProactiveAlertsPage from './ProactiveAlertsPage'

const STATUS_CONFIG = {
  healthy:  { label: 'Healthy',  icon: CheckCircle2,  color: 'text-emerald-400', bg: 'bg-emerald-500/10', ring: 'ring-emerald-500/30', dot: 'bg-emerald-400' },
  degraded: { label: 'Degraded', icon: AlertTriangle,  color: 'text-amber-400',   bg: 'bg-amber-500/10',   ring: 'ring-amber-500/30',   dot: 'bg-amber-400' },
  down:     { label: 'Down',     icon: XCircle,        color: 'text-red-400',     bg: 'bg-red-500/10',     ring: 'ring-red-500/30',     dot: 'bg-red-400' },
  error:    { label: 'Error',    icon: XCircle,        color: 'text-red-400',     bg: 'bg-red-500/10',     ring: 'ring-red-500/30',     dot: 'bg-red-400' },
  unknown:  { label: 'Unknown',  icon: HelpCircle,     color: 'text-zinc-400',    bg: 'bg-zinc-500/10',    ring: 'ring-zinc-500/30',    dot: 'bg-zinc-400' },
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.unknown
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color} ring-1 ${cfg.ring}`}>
      <Icon size={12} />
      {cfg.label}
    </span>
  )
}

function SummaryCard({ label, value, icon: Icon, color }) {
  return (
    <div className="glass hover-lift rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">{label}</span>
        <Icon size={16} className={color} />
      </div>
      <p className="text-2xl font-bold text-[var(--text-heading)]">{value}</p>
    </div>
  )
}

function Site24x7StatCard({ label, value, tone = 'muted' }) {
  const toneClass = {
    danger: 'text-red-400',
    warning: 'text-amber-400',
    good: 'text-emerald-400',
    info: 'text-sky-400',
    muted: 'text-zinc-300',
  }[tone] || 'text-zinc-300'

  return (
    <div className="glass rounded-xl px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider">{label}</p>
        <p className={`text-lg font-bold leading-none ${toneClass}`}>{value}</p>
      </div>
    </div>
  )
}

function formatCount(value) {
  return Number(value || 0).toLocaleString()
}

function TargetRow({ target, navigate }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CONFIG[target.status] || STATUS_CONFIG.unknown
  const hasAnomalies = target.anomaly_count > 0

  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--bg-input)]"
      >
        <span className={`w-2 h-2 rounded-full ${cfg.dot} flex-shrink-0`} />
        {expanded ? <ChevronDown size={14} className="text-zinc-400 flex-shrink-0" /> : <ChevronRight size={14} className="text-zinc-400 flex-shrink-0" />}
        <span className="flex-1 text-sm font-medium text-[var(--text-primary)] truncate">
          {target.target_name}
        </span>
        <span className="text-xs text-[var(--text-secondary)] hidden sm:inline">
          {target.target_type === 'site24x7_monitor' ? 'Site24x7' : target.target_type}
        </span>
        {hasAnomalies && (
          <span className="text-xs text-amber-400 font-medium">{target.anomaly_count} anomal{target.anomaly_count === 1 ? 'y' : 'ies'}</span>
        )}
        <StatusBadge status={target.status} />
        {target.last_checked && (
          <span className="text-xs text-[var(--text-secondary)] hidden md:inline">
            {new Date(target.last_checked).toLocaleTimeString()}
          </span>
        )}
      </button>
      {expanded && (
        <div className="px-4 pb-3 ml-9 space-y-2 text-xs text-[var(--text-secondary)]">
          <div className="flex flex-wrap gap-4">
            <span>ID: <span className="font-mono">{target.target_id}</span></span>
            {target.last_checked && <span>Checked: {new Date(target.last_checked).toLocaleString()}</span>}
          </div>
          {target.latest_metrics && Object.keys(target.latest_metrics).length > 0 && (
            <div>
              <p className="font-medium mb-1 text-[var(--text-primary)]">Metrics:</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(target.latest_metrics).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 rounded font-mono bg-[var(--bg-input)] border border-[var(--border)]">
                    {k}: {typeof v === 'number' ? v.toFixed(1) : String(v)}
                  </span>
                ))}
              </div>
            </div>
          )}
          {target.incident_id && (
            <button
              onClick={(e) => { e.stopPropagation(); navigate(`/incidents/${target.incident_id}`) }}
              className="inline-flex items-center gap-1 text-[var(--neon-cyan)] hover:text-[var(--color-accent-cyan)] transition-colors"
            >
              <ExternalLink size={12} /> View Incident
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function RecentCheckRow({ check }) {
  const cfg = STATUS_CONFIG[check.status] || STATUS_CONFIG.unknown
  return (
    <div className="flex items-center gap-3 px-4 py-2 text-xs border-b border-[var(--border)] text-[var(--text-secondary)]">
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} flex-shrink-0`} />
      <span className="flex-1 truncate text-[var(--text-primary)]">{check.target_name}</span>
      <StatusBadge status={check.status} />
      {check.duration_ms != null && <span className="hidden sm:inline">{check.duration_ms.toFixed(0)}ms</span>}
      <span>{new Date(check.checked_at).toLocaleTimeString()}</span>
    </div>
  )
}

const TABS = [
  { key: 'monitor', label: 'Monitor Status', icon: HeartPulse },
  { key: 'ai-alerts', label: 'AI Alerts', icon: Radar },
]

export default function HealthChecksPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') === 'ai-alerts' ? 'ai-alerts' : 'monitor'

  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [filter, setFilter] = useState('down')
  const [monitors, setMonitors] = useState(null)
  const [monitorsLoading, setMonitorsLoading] = useState(false)
  const [monitorsRefreshing, setMonitorsRefreshing] = useState(false)
  const [runResult, setRunResult] = useState(null)

  const loadDashboard = useCallback(async () => {
    try {
      setError(null)
      const data = await fetchHealthCheckDashboard()
      setDashboard(data)
    } catch (err) {
      setError(err.message || 'Failed to load health check data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
    const interval = setInterval(loadDashboard, 60000)
    return () => clearInterval(interval)
  }, [loadDashboard])

  const loadMonitors = useCallback(async (refresh = false) => {
    refresh ? setMonitorsRefreshing(true) : setMonitorsLoading(true)
    try {
      const data = await fetchMonitorInventory({ refresh })
      setMonitors(data)
    } catch {
      // non-fatal — monitor inventory is best-effort
    } finally {
      setMonitorsLoading(false)
      setMonitorsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadMonitors()
  }, [loadMonitors])

  const handleRunNow = async () => {
    setRunning(true)
    setError(null)
    try {
      const result = await triggerHealthCheck()
      setRunResult(result)
      await Promise.all([loadDashboard(), loadMonitors(true)])
    } catch (err) {
      setError(err.message || 'Failed to trigger health check')
    } finally {
      setRunning(false)
    }
  }

  const liveMonitors = monitors?.monitors || []
  const filteredLiveTargets = liveMonitors.filter((m) => {
    const s = m.site24x7_status_label || 'unknown'
    if (filter === 'all') return true
    return s === filter
  })
  const visibleLiveTargets = filteredLiveTargets.slice(0, 300)

  const summary = dashboard?.summary || {}
  const site24x7Summary = monitors?.status_summary || null

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(34,211,238,0.1))', border: '1px solid rgba(99,102,241,0.2)' }}>
            <HeartPulse size={24} className="text-[var(--neon-indigo)]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--text-heading)]">Site24x7 Health Checks</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Site24x7 monitor health and proactive incident checks
              {summary.last_run_at && (
                <span> &middot; Last run: {new Date(summary.last_run_at).toLocaleString()}</span>
              )}
            </p>
          </div>
        </div>
        {user?.role === 'admin' && activeTab === 'monitor' && (
          <button
            onClick={handleRunNow}
            disabled={running}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              running
                ? 'opacity-50 cursor-not-allowed'
                : 'hover:shadow-lg hover:shadow-[rgba(99,102,241,0.25)]'
            }`}
            style={!running ? { background: 'var(--gradient-primary)', color: '#fff' } : { background: 'var(--bg-input)', color: 'var(--text-muted)' }}
          >
            <RefreshCw size={14} className={running ? 'animate-spin' : ''} />
            {running ? 'Running...' : 'Run Now'}
          </button>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', width: 'fit-content' }}>
        {TABS.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => setSearchParams(tab.key === 'monitor' ? {} : { tab: tab.key })}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all"
              style={{
                background: isActive ? 'rgba(99,102,241,0.15)' : 'transparent',
                color: isActive ? 'var(--neon-indigo)' : 'var(--text-muted)',
                border: isActive ? '1px solid rgba(99,102,241,0.25)' : '1px solid transparent',
              }}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Proactive Alerts tab */}
      {activeTab === 'ai-alerts' && <ProactiveAlertsPage />}

      {/* Monitor Status tab */}
      {activeTab === 'monitor' && loading && (
        <div className="flex items-center justify-center h-64">
          <RefreshCw size={24} className="animate-spin text-[var(--neon-cyan)]" />
          <span className="ml-3 text-[var(--text-secondary)]">Loading health checks...</span>
        </div>
      )}

      {activeTab === 'monitor' && !loading && (<>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {runResult && (
        <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm">
          Run completed: checked {runResult.checked ?? 0}, healthy {runResult.healthy ?? 0}, degraded {runResult.degraded ?? 0}, down {runResult.down ?? 0}, incidents {runResult.incidents_created ?? 0}.
        </div>
      )}

      {/* Summary Cards */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">AIREX Proactive Snapshot (Last Run)</h2>
        <p className="text-xs text-[var(--text-muted)]">
          These counters show monitors evaluated by AIREX during the latest health-check run.
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <SummaryCard label="Evaluated" value={formatCount(summary.total_targets)} icon={Server} color="text-blue-400" />
        <SummaryCard label="Healthy" value={formatCount(summary.healthy)} icon={CheckCircle2} color="text-emerald-400" />
        <SummaryCard label="Degraded" value={formatCount(summary.degraded)} icon={AlertTriangle} color="text-amber-400" />
        <SummaryCard label="Down" value={formatCount(summary.down)} icon={XCircle} color="text-red-400" />
        <SummaryCard label="Unknown" value={formatCount(summary.unknown)} icon={HelpCircle} color="text-zinc-400" />
        <SummaryCard label="Incidents (24h)" value={formatCount(summary.incidents_created_24h)} icon={Zap} color="text-purple-400" />
      </div>

      {site24x7Summary && (
        <div className="glass rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">Site24x7 Monitor Status (Live)</h2>
              <p className="text-xs text-[var(--text-muted)]">
                Last updated {monitors?.last_synced_at ? new Date(monitors.last_synced_at).toLocaleString() : 'just now'}
              </p>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">Total Monitors: {formatCount(site24x7Summary.total_monitors)}</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            <Site24x7StatCard label="Down" value={formatCount(site24x7Summary.down)} tone="danger" />
            <Site24x7StatCard label="Critical" value={formatCount(site24x7Summary.critical)} tone="danger" />
            <Site24x7StatCard label="Trouble" value={formatCount(site24x7Summary.trouble)} tone="warning" />
            <Site24x7StatCard label="Up" value={formatCount(site24x7Summary.up)} tone="good" />
            <Site24x7StatCard label="Confirmed Anomalies" value={formatCount(site24x7Summary.confirmed_anomalies)} tone="warning" />
            <Site24x7StatCard label="Maintenance" value={formatCount(site24x7Summary.maintenance)} tone="info" />
            <Site24x7StatCard label="Discovery in Progress" value={formatCount(site24x7Summary.discovery_in_progress)} tone="info" />
            <Site24x7StatCard label="Configuration Error(s)" value={formatCount(site24x7Summary.configuration_error)} tone="danger" />
            <Site24x7StatCard label="Suspended Monitors" value={formatCount(site24x7Summary.suspended)} tone="muted" />
          </div>
        </div>
      )}

      {/* Live Filter Tabs */}
      <div className="flex items-center gap-1 flex-wrap">
        {[
          ['all', liveMonitors.length],
          ['down', site24x7Summary?.down],
          ['critical', site24x7Summary?.critical],
          ['trouble', site24x7Summary?.trouble],
          ['up', site24x7Summary?.up],
          ['maintenance', site24x7Summary?.maintenance],
          ['suspended', site24x7Summary?.suspended],
          ['configuration_error', site24x7Summary?.configuration_error],
          ['discovery_in_progress', site24x7Summary?.discovery_in_progress],
        ].map(([f, c]) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-[var(--glow-indigo)] text-[var(--neon-indigo)] border border-[rgba(99,102,241,0.3)]'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-input)] border border-transparent'
            }`}
          >
            {f === 'all'
              ? `All (${formatCount(c)})`
              : `${String(f).replace(/_/g, ' ').replace(/\b\w/g, (x) => x.toUpperCase())} (${formatCount(c)})`}
          </button>
        ))}
      </div>

      {/* Live Targets List */}
      <div className="glass rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-elevated)]">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            <Activity size={14} className="inline mr-2 text-[var(--neon-cyan)]" />
            Site24x7 Live Targets ({formatCount(filteredLiveTargets.length)})
          </h2>
        </div>
        {filteredLiveTargets.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            No targets match the selected live status filter.
          </div>
        ) : (
          <>
            {visibleLiveTargets.map((m) => {
              const liveStatus = m.site24x7_status_label || 'unknown'
              const mappedStatus =
                liveStatus === 'up'
                  ? 'healthy'
                  : liveStatus === 'trouble' || liveStatus === 'critical'
                    ? 'degraded'
                    : liveStatus === 'down' || liveStatus === 'configuration_error'
                      ? 'down'
                      : 'unknown'
              const t = {
                target_type: 'site24x7_monitor',
                target_id: m.monitor_id,
                target_name: m.monitor_name,
                status: mappedStatus,
                last_checked: m.last_checked_at,
                incident_id: m.last_incident_id,
              }
              return <TargetRow key={`live-${m.monitor_id}`} target={t} navigate={navigate} />
            })}
            {filteredLiveTargets.length > visibleLiveTargets.length && (
              <div className="px-4 py-3 text-xs text-[var(--text-muted)] border-t border-[var(--border)]">
                Showing first {formatCount(visibleLiveTargets.length)} results. Use status filters to narrow large lists.
              </div>
            )}
          </>
        )}
      </div>

      {/* Recent Checks */}
      {dashboard?.recent_checks?.length > 0 && (
        <div className="glass rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-elevated)]">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              <Clock size={14} className="inline mr-2 text-[var(--neon-purple)]" />
              Recent Checks (last 50)
            </h2>
          </div>
          {dashboard.recent_checks.slice(0, 20).map(c => (
            <RecentCheckRow key={c.id} check={c} />
          ))}
        </div>
      )}

      {/* Monitor Inventory — only shown when Site24x7 is enabled */}
      {monitors?.site24x7_enabled && (
        <div className="glass rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-elevated)] flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">
              <Server size={14} className="inline mr-2 text-[var(--neon-cyan)]" />
              Site24x7 Monitor Inventory ({monitors.total})
            </h2>
            <button
              onClick={() => loadMonitors(true)}
              disabled={monitorsRefreshing}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
            >
              <RefreshCw size={11} className={monitorsRefreshing ? 'animate-spin' : ''} />
              {monitorsRefreshing ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          {monitorsLoading ? (
            <div className="px-4 py-6 space-y-2">
              {[1, 2, 3].map(i => <div key={i} className="h-8 skeleton rounded" />)}
            </div>
          ) : monitors.monitors?.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
              No monitors returned from Site24x7.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-input)' }}>
                    {['Name', 'Type', 'AIREX Status', 'Site24x7 Status', 'Last Checked', 'Incident'].map(h => (
                      <th key={h} className="px-4 py-2 text-left font-medium text-[var(--text-muted)] uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {monitors.monitors.map(m => {
                    const cfg = STATUS_CONFIG[m.current_status] || STATUS_CONFIG.unknown
                    return (
                      <tr key={m.monitor_id} style={{ borderBottom: '1px solid var(--border)' }} className="hover:bg-[var(--bg-input)] transition-colors">
                        <td className="px-4 py-2.5 text-[var(--text-primary)] font-medium">{m.monitor_name}</td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)]">{m.monitor_type || '—'}</td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color} ring-1 ${cfg.ring}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                            {cfg.label}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                          {m.site24x7_status_label
                            ? m.site24x7_status_label.replace(/_/g, ' ')
                            : 'unknown'}
                        </td>
                        <td className="px-4 py-2.5 text-[var(--text-secondary)] font-mono">
                          {m.last_checked_at ? new Date(m.last_checked_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-2.5">
                          {m.last_incident_id ? (
                            <button
                              onClick={() => navigate(`/incidents/${m.last_incident_id}`)}
                              className="inline-flex items-center gap-1 text-[var(--neon-cyan)] hover:underline"
                            >
                              <ExternalLink size={11} /> View
                            </button>
                          ) : (
                            <span className="text-[var(--text-muted)]">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {monitors.last_synced_at && (
            <div className="px-4 py-2 text-xs text-[var(--text-muted)] border-t border-[var(--border)]">
              Synced {new Date(monitors.last_synced_at).toLocaleString()}
            </div>
          )}
        </div>
      )}
      </>)}
    </div>
  )
}
