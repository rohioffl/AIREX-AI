import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  HeartPulse, RefreshCw, AlertTriangle, CheckCircle2,
  XCircle, HelpCircle, Clock, Activity, ChevronDown,
  ChevronRight, ExternalLink, Zap, Server
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchHealthCheckDashboard, triggerHealthCheck } from '../services/api'

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

export default function HealthChecksPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [filter, setFilter] = useState('all')

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

  const handleRunNow = async () => {
    setRunning(true)
    try {
      await triggerHealthCheck()
      await loadDashboard()
    } catch (err) {
      setError(err.message || 'Failed to trigger health check')
    } finally {
      setRunning(false)
    }
  }

  const filteredTargets = dashboard?.targets?.filter(t => {
    if (filter === 'all') return true
    return t.status === filter
  }) || []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw size={24} className="animate-spin text-[var(--neon-cyan)]" />
        <span className="ml-3 text-[var(--text-secondary)]">Loading health checks...</span>
      </div>
    )
  }

  const summary = dashboard?.summary || {}

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg" style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(34,211,238,0.1))', border: '1px solid rgba(99,102,241,0.2)' }}>
            <HeartPulse size={24} className="text-[#818cf8]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--text-heading)]">Proactive Health Checks</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Continuous monitoring of infrastructure health
              {summary.last_run_at && (
                <span> &middot; Last run: {new Date(summary.last_run_at).toLocaleString()}</span>
              )}
            </p>
          </div>
        </div>
        {user?.role === 'admin' && (
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

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <SummaryCard label="Total" value={summary.total_targets || 0} icon={Server} color="text-blue-400" />
        <SummaryCard label="Healthy" value={summary.healthy || 0} icon={CheckCircle2} color="text-emerald-400" />
        <SummaryCard label="Degraded" value={summary.degraded || 0} icon={AlertTriangle} color="text-amber-400" />
        <SummaryCard label="Down" value={summary.down || 0} icon={XCircle} color="text-red-400" />
        <SummaryCard label="Unknown" value={summary.unknown || 0} icon={HelpCircle} color="text-zinc-400" />
        <SummaryCard label="Incidents (24h)" value={summary.incidents_created_24h || 0} icon={Zap} color="text-purple-400" />
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 flex-wrap">
        {['all', 'healthy', 'degraded', 'down', 'unknown', 'error'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === f
                ? 'bg-[var(--glow-indigo)] text-[var(--neon-indigo)] border border-[rgba(99,102,241,0.3)]'
                : 'text-[var(--text-muted)] hover:bg-[var(--bg-input)] border border-transparent'
            }`}
          >
            {f === 'all' ? `All (${dashboard?.targets?.length || 0})` : `${f.charAt(0).toUpperCase() + f.slice(1)} (${summary[f] || 0})`}
          </button>
        ))}
      </div>

      {/* Targets List */}
      <div className="glass rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--bg-elevated)]">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            <Activity size={14} className="inline mr-2 text-[var(--neon-cyan)]" />
            Monitored Targets ({filteredTargets.length})
          </h2>
        </div>
        {filteredTargets.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            {dashboard?.targets?.length === 0
              ? 'No health checks have run yet. Click "Run Now" to start.'
              : 'No targets match the selected filter.'
            }
          </div>
        ) : (
          filteredTargets.map(t => (
            <TargetRow key={`${t.target_type}-${t.target_id}`} target={t} navigate={navigate} />
          ))
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
    </div>
  )
}
