import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, Bell, Clock, Mail,
  ChevronRight, Zap, ShieldAlert, AlertOctagon, Radio
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import StateBadge from '../components/common/StateBadge'
import SeverityBadge from '../components/common/SeverityBadge'
import ConnectionBanner from '../components/common/ConnectionBanner'
import { formatTimestamp, truncateId, buildAcknowledgeMailto } from '../utils/formatters'

const ACTIVE_STATES = [
  'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY',
  'AWAITING_APPROVAL', 'EXECUTING', 'VERIFYING',
]

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

const ALERT_FILTERS = [
  { key: 'all', label: 'All Active', icon: Bell },
  { key: 'critical', label: 'Critical', icon: AlertOctagon },
  { key: 'action', label: 'Needs Action', icon: Zap },
  { key: 'investigating', label: 'Investigating', icon: Radio },
]

export default function AlertsPage() {
  const { incidents, loading, error, connected, reconnecting } = useIncidents()
  const [alertFilter, setAlertFilter] = useState('all')

  const activeAlerts = useMemo(() => {
    const active = incidents.filter(i => ACTIVE_STATES.includes(i.state))
    const sorted = active.sort((a, b) => {
      const sevDiff = (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4)
      if (sevDiff !== 0) return sevDiff
      return new Date(b.created_at) - new Date(a.created_at)
    })

    switch (alertFilter) {
      case 'critical':
        return sorted.filter(i => i.severity === 'CRITICAL')
      case 'action':
        return sorted.filter(i => ['AWAITING_APPROVAL', 'RECOMMENDATION_READY'].includes(i.state))
      case 'investigating':
        return sorted.filter(i => ['INVESTIGATING', 'RECEIVED'].includes(i.state))
      default:
        return sorted
    }
  }, [incidents, alertFilter])

  const counts = useMemo(() => {
    const active = incidents.filter(i => ACTIVE_STATES.includes(i.state))
    return {
      all: active.length,
      critical: active.filter(i => i.severity === 'CRITICAL').length,
      action: active.filter(i => ['AWAITING_APPROVAL', 'RECOMMENDATION_READY'].includes(i.state)).length,
      investigating: active.filter(i => ['INVESTIGATING', 'RECEIVED'].includes(i.state)).length,
    }
  }, [incidents])

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} />

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
        activeAlerts.length === 0 ? (
          <div className="glass rounded-xl py-20 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full mb-4" style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399' }}>
              <ShieldAlert size={24} />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>All clear</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>No active alerts matching this filter.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {activeAlerts.map(alert => (
              <AlertRow key={alert.id} alert={alert} />
            ))}
          </div>
        )
      )}
    </div>
  )
}


function AlertRow({ alert }) {
  const isUrgent = alert.severity === 'CRITICAL' || alert.state === 'AWAITING_APPROVAL'
  const needsAction = alert.state === 'AWAITING_APPROVAL' || alert.state === 'RECOMMENDATION_READY'

  return (
    <Link
      to={`/incidents/${alert.id}`}
      className="group block glass glass-hover rounded-xl transition-all"
      style={{
        borderLeft: isUrgent ? '3px solid #fb7185' : '3px solid transparent',
      }}
    >
      <div className="flex items-center gap-4 px-5 py-4">
        {/* Severity Icon */}
        <div className="flex-shrink-0">
          {alert.severity === 'CRITICAL' ? (
            <div className="relative">
              <AlertOctagon size={20} style={{ color: '#fb7185' }} />
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full" style={{ background: '#f43f5e', animation: 'pulse 2s infinite' }} />
            </div>
          ) : alert.severity === 'HIGH' ? (
            <AlertTriangle size={20} style={{ color: '#fb923c' }} />
          ) : (
            <Bell size={20} style={{ color: 'var(--text-muted)' }} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="truncate" style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)' }}>
              {alert.title}
            </span>
            {needsAction && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ background: 'rgba(251,191,36,0.12)', color: '#fbbf24', fontSize: 10, fontWeight: 700 }}>
                <Zap size={9} />
                ACTION NEEDED
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#818cf8' }}>
              {truncateId(alert.id)}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)', padding: '1px 6px', borderRadius: 4 }}>
              {alert.alert_type}
            </span>
            <span className="flex items-center gap-1" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              <Clock size={10} />
              {formatTimestamp(alert.created_at)}
            </span>
          </div>
        </div>

        {/* Actions + Badges */}
        <div className="flex-shrink-0 flex items-center gap-2">
          <a
            href={buildAcknowledgeMailto(alert)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md transition-all opacity-0 group-hover:opacity-100"
            style={{
              fontSize: 11,
              fontWeight: 700,
              background: 'rgba(99,102,241,0.1)',
              color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.2)',
            }}
            title="Acknowledge — open Gmail draft"
          >
            <Mail size={11} />
            ACK
          </a>
          <SeverityBadge severity={alert.severity} />
          <StateBadge state={alert.state} />
          <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} className="opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </Link>
  )
}
