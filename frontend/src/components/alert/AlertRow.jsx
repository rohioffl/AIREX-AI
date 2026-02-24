import { Link } from 'react-router-dom'
import {
  AlertOctagon,
  AlertTriangle,
  Bell,
  Clock,
  ChevronRight,
  Mail,
  Zap,
} from 'lucide-react'
import SeverityBadge from '../common/SeverityBadge'
import StateBadge from '../common/StateBadge'
import { formatTimestamp, truncateId, buildAcknowledgeMailto } from '../../utils/formatters'

export default function AlertRow({
  alert,
  badgeLabel,
  badgeColor = '#fbbf24',
  badgeIcon: BadgeIcon,
  highlightColor,
  disableAck = false,
  manualReview = false,
  manualReason,
  manualAt,
}) {
  const isUrgent = alert.severity === 'CRITICAL' || alert.state === 'AWAITING_APPROVAL'
  const needsAction = alert.state === 'AWAITING_APPROVAL' || alert.state === 'RECOMMENDATION_READY'
  const manualNote = (manualReason || '').trim()

  const borderColor = highlightColor
    ? highlightColor
    : manualReview
      ? '#f87171'
      : isUrgent
        ? '#fb7185'
        : 'transparent'

  return (
    <Link
      to={`/incidents/${alert.id}`}
      className="group block glass glass-hover rounded-xl transition-all"
      style={{
        borderLeft: `3px solid ${borderColor}`,
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
            {(!badgeLabel && needsAction) && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ background: 'rgba(251,191,36,0.12)', color: '#fbbf24', fontSize: 10, fontWeight: 700 }}>
                <Zap size={9} />
                ACTION NEEDED
              </span>
            )}
            {manualReview && !badgeLabel && (
              <span
                className="flex-shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ background: 'rgba(248,113,113,0.15)', color: '#f87171', fontSize: 10, fontWeight: 700 }}
              >
                Manual Review
              </span>
            )}
            {badgeLabel && (
              <span
                className="flex-shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{
                  background: `${badgeColor}1f`,
                  color: badgeColor,
                  fontSize: 10,
                  fontWeight: 700,
                }}
              >
                {BadgeIcon ? <BadgeIcon size={10} /> : null}
                {badgeLabel}
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
          {manualNote && (
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
              <span style={{ color: '#f87171', fontWeight: 600 }}>Operator note:</span> {manualNote}
              {manualAt && (
                <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>
                  ({formatTimestamp(manualAt)})
                </span>
              )}
            </p>
          )}
        </div>

        {/* Actions + Badges */}
        <div className="flex-shrink-0 flex items-center gap-2">
          {!disableAck && (
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
          )}
          <SeverityBadge severity={alert.severity} />
          <StateBadge state={alert.state} />
          <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} className="opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </Link>
  )
}
