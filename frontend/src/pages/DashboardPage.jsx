import { useMemo, useState } from 'react'
import { AlertTriangle, RefreshCcw, TrendingUp, Bell, Activity, Clock, CheckCircle } from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import ConnectionBanner from '../components/common/ConnectionBanner'
import MetricCard from '../components/common/MetricCard'
import SystemGraph from '../components/common/SystemGraph'
import AlertRow from '../components/alert/AlertRow'
import { formatTimestamp } from '../utils/formatters'

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
  const [graphType, setGraphType] = useState('area')

  const latestFive = useMemo(() => {
    const sorted = [...incidents].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    return sorted.slice(0, 5)
  }, [incidents])

  const summary = useMemo(() => {
    let active = 0
    let critical = 0
    let resolvedToday = 0
    const today = new Date().toDateString()

    incidents.forEach((i) => {
      if (ACTIVE_STATES.includes(i.state)) active += 1
      if (i.severity === 'CRITICAL') critical += 1
      if (TERMINAL_STATES.includes(i.state)) {
        if (new Date(i.updated_at).toDateString() === today) resolvedToday += 1
      }
    })

    return { active, critical, resolvedToday }
  }, [incidents])

  const lastUpdated = latestFive[0]?.updated_at ? formatTimestamp(latestFive[0].updated_at) : '—'

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} onRetry={reload} />

      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <TrendingUp size={26} style={{ color: '#22d3ee' }} />
            Command Dashboard
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Snapshot of the five most recent alerts. Last updated {lastUpdated}.
          </p>
        </div>
        <button
          onClick={() => reload()}
          className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg"
          style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          <RefreshCcw size={14} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Active" value={String(summary.active)} trend="Awaiting resolution" trendType="neutral" icon={Bell} />
        <MetricCard title="Critical" value={String(summary.critical)} trend={summary.critical ? 'Needs attention' : 'Stable'} trendType={summary.critical ? 'negative' : 'positive'} icon={AlertTriangle} isCritical={summary.critical > 0} />
        <MetricCard title="Resolved (24h)" value={String(summary.resolvedToday)} trend="Closed in last day" trendType="positive" icon={CheckCircle} />
        <MetricCard title="Live Sessions" value={connected ? '1' : '0'} trend={connected ? 'Online' : 'Offline'} trendType={connected ? 'positive' : 'negative'} icon={Activity} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SystemGraph incidents={incidents} type={graphType} />
        </div>
        <div className="glass p-5 flex flex-col gap-4">
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Telemetry</span>
          <div className="flex-1 flex flex-col gap-3">
            {[
              { label: 'MTTR', value: '4m 23s', color: '#10b981' },
              { label: 'Avg Investigation', value: '45s', color: '#6366f1' },
              { label: 'AI Confidence', value: '87%', color: '#a855f7' },
              { label: 'Auto-resolved', value: `${summary.resolvedToday}`, color: '#22d3ee' },
            ].map((s) => (
              <div key={s.label} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.label}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: s.color }}>{s.value}</span>
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-auto">
            {['area', 'bar'].map((t) => (
              <button
                key={t}
                onClick={() => setGraphType(t)}
                className="flex-1 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-all"
                style={{
                  background: graphType === t ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                  color: graphType === t ? '#818cf8' : 'var(--text-muted)',
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
          {[...Array(3)].map((_, idx) => <div key={idx} className="glass rounded-xl h-20 shimmer" />)}
        </div>
      )}

      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid #f43f5e', background: 'rgba(244,63,94,0.03)', fontSize: 14, color: '#fb7185' }}>
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
