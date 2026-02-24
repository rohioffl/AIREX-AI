import { useMemo, useState } from 'react'
import {
  AlertTriangle, Bell,
  ShieldAlert, AlertOctagon, Radio, Zap
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import ConnectionBanner from '../components/common/ConnectionBanner'
import AlertRow from '../components/alert/AlertRow'

const ACTION_STATES = ['RECOMMENDATION_READY', 'AWAITING_APPROVAL']
const INVESTIGATING_STATES = ['RECEIVED', 'INVESTIGATING']

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

const ALERT_FILTERS = [
  { key: 'all', label: 'All Active', icon: Bell },
  { key: 'critical', label: 'Critical', icon: AlertOctagon },
  { key: 'action', label: 'Needs Action', icon: Zap },
  { key: 'investigating', label: 'Investigating', icon: Radio },
]

export default function AlertsPage() {
  const { incidents, loading, error, connected, reconnecting, reload } = useIncidents()
  const [alertFilter, setAlertFilter] = useState('all')

  const visibleAlerts = useMemo(() => {
    const list = incidents
      .filter(i => i.state !== 'REJECTED')
      .map(i => ({ ...i }))
    const sorted = list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

    switch (alertFilter) {
      case 'critical':
        return sorted.filter(i => i.severity === 'CRITICAL')
      case 'action':
        return sorted.filter(i => ACTION_STATES.includes(i.state))
      case 'investigating':
        return sorted.filter(i => INVESTIGATING_STATES.includes(i.state))
      default:
        return sorted
    }
  }, [incidents, alertFilter])

  const counts = useMemo(() => {
    const list = incidents.filter(i => i.state !== 'REJECTED')
    return {
      all: list.length,
      critical: list.filter(i => i.severity === 'CRITICAL').length,
      action: list.filter(i => ACTION_STATES.includes(i.state)).length,
      investigating: list.filter(i => INVESTIGATING_STATES.includes(i.state)).length,
    }
  }, [incidents])

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} onRetry={reload} />

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <AlertTriangle size={24} style={{ color: '#fb923c' }} />
            Active Alerts
            {counts.all > 0 && (
              <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full text-xs font-bold"
                style={{ background: counts.critical > 0 ? 'rgba(244,63,94,0.15)' : 'rgba(251,146,60,0.15)', color: counts.critical > 0 ? '#fb7185' : '#fb923c' }}>
                {counts.all}
              </span>
            )}
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Incidents requiring attention, sorted by severity.
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        {ALERT_FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setAlertFilter(f.key)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{
              background: alertFilter === f.key ? 'rgba(99,102,241,0.1)' : 'var(--bg-elevated)',
              color: alertFilter === f.key ? '#818cf8' : 'var(--text-secondary)',
              border: `1px solid ${alertFilter === f.key ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <f.icon size={14} />
            {f.label}
            <span className="ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-bold"
              style={{
                background: alertFilter === f.key ? 'rgba(99,102,241,0.2)' : 'var(--bg-input)',
                color: alertFilter === f.key ? '#a5b4fc' : 'var(--text-muted)',
              }}>
              {counts[f.key]}
            </span>
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <div key={i} className="glass rounded-xl h-20 shimmer" />)}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid #f43f5e', background: 'rgba(244,63,94,0.03)', fontSize: 14, color: '#fb7185' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

{/* Alert List */}
      {!loading && !error && (
        visibleAlerts.length === 0 ? (
          <div className="glass rounded-xl py-20 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full mb-4" style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399' }}>
              <ShieldAlert size={24} />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>All clear</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>No active alerts matching this filter.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {visibleAlerts.map(alert => {
              const manualReason = alert.meta?._manual_review_reason
              const manualReview = Boolean(alert.meta?._manual_review_required || manualReason)
              return (
                <AlertRow
                  key={alert.id}
                  alert={alert}
                  manualReview={manualReview}
                  manualReason={manualReason}
                  manualAt={alert.meta?._manual_review_at}
                />
              )
            })}
          </div>
        )
      )}
    </div>
  )
}
