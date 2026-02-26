import { Link } from 'react-router-dom'
import {
  AlertOctagon,
  AlertTriangle,
  Bell,
  Clock,
  ChevronRight,
  Zap,
  Server,
  Repeat,
  Activity,
} from 'lucide-react'
import SeverityBadge from '../common/SeverityBadge'
import StateBadge from '../common/StateBadge'
import { formatRelativeTime, truncateId } from '../../utils/formatters'

export default function AlertRow({
  alert,
  badgeLabel,
  badgeColor = '#fbbf24',
  badgeIcon: BadgeIcon,
  highlightColor,
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

  // Extract host from title if available, otherwise use host_key
  const titleHost = alert.title?.match(/on\s+([^\s]+)/i)?.[1]
  const displayHost = alert.host_key || titleHost || null
  const showHost = displayHost && !alert.title?.includes(displayHost)

  const alertCount = alert.meta?._alert_count > 1 ? alert.meta._alert_count : null
  const durationSec = alert.meta?._alert_duration_seconds
  const durationMin = durationSec ? Math.round(durationSec / 60) : null
  const incidentReason = alert.meta?.INCIDENT_REASON || alert.meta?.INCIDENT_DETAILS

  const isLightMode = document.body.classList.contains('light-mode')
  
  return (
    <div
      className="group glass glass-hover rounded-lg relative overflow-hidden"
      style={{
        borderLeft: `3px solid ${borderColor}`,
        width: '100%',
        boxSizing: 'border-box',
        background: isLightMode ? '#FFFFFF' : (isUrgent ? 'rgba(251,113,133,0.02)' : 'transparent'),
        borderTop: isLightMode ? '1px solid #E5E7EB' : 'none',
        borderRight: isLightMode ? '1px solid #E5E7EB' : 'none',
        borderBottom: isLightMode ? '1px solid #E5E7EB' : 'none',
        transition: 'background 160ms ease, border-top-color 160ms ease, border-right-color 160ms ease, border-bottom-color 160ms ease, box-shadow 160ms ease, transform 160ms ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-1px)'
        if (isLightMode) {
          // Light mode: subtle orange warmth
          e.currentTarget.style.background = 'var(--brand-orange-soft-light)'
          e.currentTarget.style.borderTopColor = '#FDBA74'
          e.currentTarget.style.borderRightColor = '#FDBA74'
          e.currentTarget.style.borderBottomColor = '#FDBA74'
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(249,115,22,0.12)'
        } else {
          // Dark mode: warm orange glow
          e.currentTarget.style.background = 'var(--brand-orange-soft-dark)'
          e.currentTarget.style.borderTop = '1px solid rgba(249,115,22,0.5)'
          e.currentTarget.style.borderRight = '1px solid rgba(249,115,22,0.5)'
          e.currentTarget.style.borderBottom = '1px solid rgba(249,115,22,0.5)'
          e.currentTarget.style.boxShadow = '0 6px 18px rgba(249,115,22,0.15)'
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        if (isLightMode) {
          e.currentTarget.style.background = '#FFFFFF'
          e.currentTarget.style.borderTopColor = '#E5E7EB'
          e.currentTarget.style.borderRightColor = '#E5E7EB'
          e.currentTarget.style.borderBottomColor = '#E5E7EB'
          e.currentTarget.style.boxShadow = 'none'
        } else {
          e.currentTarget.style.background = isUrgent ? 'rgba(251,113,133,0.02)' : 'transparent'
          e.currentTarget.style.borderTop = 'none'
          e.currentTarget.style.borderRight = 'none'
          e.currentTarget.style.borderBottom = 'none'
          e.currentTarget.style.boxShadow = 'none'
        }
      }}
    >
      <Link
        to={`/incidents/${alert.id}`}
        className="flex items-center gap-3 px-4 py-3"
        style={{ textDecoration: 'none', color: 'inherit', display: 'flex', width: '100%', boxSizing: 'border-box' }}
      >
        {/* Severity Icon - More compact */}
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

        {/* Content - More compact */}
        <div className="flex-1 min-w-0">
          {/* Title Row */}
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="truncate" style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.3 }}>
              {alert.title}
            </span>
            {(!badgeLabel && needsAction) && (
              <span className="flex-shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24', fontSize: 10, fontWeight: 700 }}>
                <Zap size={9} />
                ACTION
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
                {BadgeIcon ? <BadgeIcon size={9} /> : null}
                {badgeLabel}
              </span>
            )}
          </div>
          
          {/* Compact Info Row - All on one line */}
          <div className="flex items-center gap-2.5 flex-wrap" style={{ fontSize: 11 }}>
            <span style={{ fontFamily: 'var(--font-mono)', color: '#818cf8', fontWeight: 600 }}>
              {truncateId(alert.id)}
            </span>
            <span style={{ 
              fontFamily: 'var(--font-mono)', 
              color: 'var(--text-primary)', 
              background: 'var(--bg-input)', 
              padding: '2px 6px', 
              borderRadius: 4,
              fontWeight: 500,
              border: '1px solid var(--border)'
            }}>
              {alert.alert_type}
            </span>
            {showHost && (
              <span className="flex items-center gap-1" style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
                <Server size={10} />
                {displayHost}
              </span>
            )}
            <span className="flex items-center gap-1" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              <Clock size={10} />
              {formatRelativeTime(alert.created_at)}
            </span>
            {(alertCount || durationMin) && (
              <span className="flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
                {alertCount && (
                  <>
                    <Repeat size={10} />
                    {alertCount}×
                  </>
                )}
                {durationMin && (
                  <>
                    <Activity size={10} style={{ marginLeft: alertCount ? 0 : 0 }} />
                    {durationMin}m
                  </>
                )}
              </span>
            )}
          </div>
          
          {/* Incident Reason - Truncated */}
          {incidentReason && (
            <div className="mt-1.5" style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              <span className="truncate block max-w-2xl">
                {String(incidentReason).substring(0, 80)}
                {String(incidentReason).length > 80 ? '...' : ''}
              </span>
            </div>
          )}
          
          {/* Manual Note */}
          {manualNote && (
            <div className="mt-1.5 p-1.5 rounded" style={{ background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.1)' }}>
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                <span style={{ color: '#f87171', fontWeight: 600 }}>Note:</span> {manualNote}
                {manualAt && (
                  <span style={{ color: 'var(--text-muted)', marginLeft: 4, fontSize: 10 }}>
                    ({formatRelativeTime(manualAt)})
                  </span>
                )}
              </p>
            </div>
          )}
        </div>

        {/* Actions + Badges - Compact */}
        <div className="flex-shrink-0 flex items-center gap-2">
          <SeverityBadge severity={alert.severity} />
          <StateBadge state={alert.state} />
          <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} className="opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </Link>
    </div>
  )
}
