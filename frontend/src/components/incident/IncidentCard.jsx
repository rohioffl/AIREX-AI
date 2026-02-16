import { Link } from 'react-router-dom'
import { Clock, ChevronRight } from 'lucide-react'
import StateBadge from '../common/StateBadge'
import SeverityBadge from '../common/SeverityBadge'
import { truncateId, formatTimestamp } from '../../utils/formatters'

export default function IncidentCard({ incident }) {
  const totalRetries =
    (incident.investigation_retry_count || 0) +
    (incident.execution_retry_count || 0) +
    (incident.verification_retry_count || 0)

  return (
    <Link to={`/incidents/${incident.id}`} className="group block glass glass-hover rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span
          className="cursor-copy"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}
          title={incident.id}
          onClick={(e) => { e.preventDefault(); navigator.clipboard.writeText(incident.id) }}
        >
          {truncateId(incident.id)}
        </span>
        <StateBadge state={incident.state} />
      </div>

      <h3 className="truncate leading-snug" style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-heading)' }}>
        {incident.title}
      </h3>

      <div className="mt-4 flex items-center gap-2 flex-wrap">
        <span
          className="rounded-md px-2 py-0.5"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
        >
          {incident.alert_type}
        </span>
        <SeverityBadge severity={incident.severity} />
        {totalRetries > 0 && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#f59e0b' }}>retry {totalRetries}/3</span>
        )}
      </div>

      <div className="mt-4 pt-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--border)' }}>
        <span className="flex items-center gap-1" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
          <Clock size={11} />
          {formatTimestamp(incident.created_at)}
        </span>
        <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
      </div>
    </Link>
  )
}
