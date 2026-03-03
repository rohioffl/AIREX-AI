import { useMemo, useState } from 'react'
import { AlertTriangle, Ban, ShieldX, AlertOctagon } from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import ConnectionBanner from '../components/common/ConnectionBanner'
import AlertRow from '../components/alert/AlertRow'

const SEVERITY_FILTERS = [
  { key: 'all', label: 'All', color: '#94a3b8' },
  { key: 'CRITICAL', label: 'Critical', color: '#fb7185' },
  { key: 'HIGH', label: 'High', color: '#fb923c' },
  { key: 'MEDIUM', label: 'Medium', color: '#22d3ee' },
  { key: 'LOW', label: 'Low', color: '#10b981' },
]

export default function RejectedPage() {
  const { incidents, loading, error, connected, reconnecting, reload } = useIncidents({ state: 'REJECTED' })
  const [severityFilter, setSeverityFilter] = useState('all')

  const filtered = useMemo(() => {
    const onlyRejected = incidents.filter((i) => i.state === 'REJECTED')
    if (severityFilter === 'all') return onlyRejected
    return onlyRejected.filter((i) => i.severity === severityFilter)
  }, [incidents, severityFilter])

  const counts = useMemo(() => {
    const base = { all: 0, CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }
    incidents.forEach((inc) => {
      if (inc.state !== 'REJECTED') return
      base.all += 1
      if (base[inc.severity] != null) base[inc.severity] += 1
    })
    return base
  }, [incidents])

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} onRetry={reload} />

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <Ban size={24} style={{ color: '#f87171' }} />
            Rejected Alerts
            {counts.all > 0 && (
              <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full text-xs font-bold"
                style={{ background: 'rgba(248,113,113,0.15)', color: '#f87171' }}>
                {counts.all}
              </span>
            )}
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Incidents that were skipped by operators. Review before archiving.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {SEVERITY_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setSeverityFilter(f.key)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{
              background: severityFilter === f.key ? `${f.color}1a` : 'var(--bg-elevated)',
              color: severityFilter === f.key ? f.color : 'var(--text-secondary)',
              border: `1px solid ${severityFilter === f.key ? `${f.color}33` : 'var(--border)'}`,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {f.key === 'CRITICAL' ? <AlertOctagon size={14} /> : f.key === 'HIGH' ? <AlertTriangle size={14} /> : <ShieldX size={14} />}
            {f.label}
            <span className="ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-bold"
              style={{
                background: severityFilter === f.key ? `${f.color}33` : 'var(--bg-input)',
                color: severityFilter === f.key ? f.color : 'var(--text-muted)',
              }}>
              {counts[f.key] ?? counts.all}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, idx) => (
            <div key={idx} className="glass rounded-xl h-20 skeleton" />
          ))}
        </div>
      )}

      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid #f43f5e', background: 'rgba(244,63,94,0.03)', fontSize: 14, color: '#fb7185' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {!loading && !error && (
        filtered.length === 0 ? (
          <div className="glass rounded-xl py-20 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full mb-4 hover-lift" style={{ background: 'rgba(248,113,113,0.12)', color: '#f87171' }}>
              <ShieldX size={24} />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>No rejected alerts</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>When an alert is skipped, it will appear here.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((alert) => (
              <AlertRow
                key={alert.id}
                alert={alert}
                badgeLabel="REJECTED"
                badgeColor="#f87171"
                badgeIcon={Ban}
                highlightColor="#f87171"
                disableAck
                manualReview
                manualReason={alert.meta?._manual_review_reason}
                manualAt={alert.meta?._manual_review_at}
              />
            ))}
          </div>
        )
      )}
    </div>
  )
}
