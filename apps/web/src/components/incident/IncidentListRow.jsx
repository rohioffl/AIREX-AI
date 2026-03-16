import { Link } from 'react-router-dom'
import {
  Radio,
  Repeat,
  Clock,
  AlertTriangle,
  GaugeCircle,
  Activity,
  ArrowUpRight,
  ChevronRight,
} from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import StateBadge from '../common/StateBadge'
import SeverityBadge from '../common/SeverityBadge'
import { formatTimestamp, truncateId, formatDuration } from '../../utils/formatters'

const SEVERITY_SHADES = {
  CRITICAL: 'var(--color-accent-red)',
  HIGH: 'var(--brand-orange)',
  MEDIUM: 'var(--color-accent-amber)',
  LOW: 'var(--color-accent-green)',
}

export default function IncidentListRow({ incident }) {
  const { isDark } = useTheme()
  const meta = incident.meta || {}
  const alertCount = meta._alert_count != null ? Number(meta._alert_count) : 1
  const durationSec = meta._alert_duration_seconds != null ? Number(meta._alert_duration_seconds) : null
  const unstable = Boolean(meta._unstable)
  const cloud = meta._cloud || meta.cloud
  const tenant = meta._tenant_name || meta.tenant
  const manualReason = typeof meta._manual_review_reason === 'string' ? meta._manual_review_reason.trim() : ''
  const manualReview = Boolean(meta._manual_review_required || manualReason)
  const manualAt = meta._manual_review_at ? formatTimestamp(String(meta._manual_review_at)) : null
  const accent = manualReview ? 'var(--color-accent-red)' : (SEVERITY_SHADES[incident.severity] || 'var(--brand-orange)')

  return (
    <Link
      to={`/incidents/${incident.id}`}
      className="block rounded-2xl relative overflow-hidden transition-all"
      style={{
        background: isDark ? 'rgba(255,255,255,0.02)' : '#FFFFFF',
        border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid #E5E7EB',
        boxShadow: isDark ? 'none' : '0 1px 2px rgba(0,0,0,0.04)',
        textDecoration: 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.04)' : '#F9FAFB'
        e.currentTarget.style.borderColor = isDark ? 'rgba(255,255,255,0.1)' : '#D1D5DB'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.02)' : '#FFFFFF'
        e.currentTarget.style.borderColor = isDark ? 'rgba(255,255,255,0.06)' : '#E5E7EB'
      }}
    >
      {/* Severity accent bar */}
      <div
        className="absolute inset-y-3 left-3 w-[3px] rounded-full"
        style={{ background: accent, opacity: 0.85 }}
      />
      <div className="pl-6 pr-4 py-3 flex items-center gap-4">
        <div className="flex-1 min-w-0 space-y-2">
          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-2 text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            <span>{truncateId(incident.id)}</span>
            <span>• {formatTimestamp(incident.created_at)}</span>
            {tenant && <span>• tenant {tenant}</span>}
          </div>
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={incident.severity} />
            <StateBadge state={incident.state} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{incident.alert_type}</span>
            {cloud && (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--text-secondary)', background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid #E5E7EB' }}>
                <Radio size={11} /> {cloud}
              </span>
            )}
            {manualReview && (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--color-accent-red)', background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.25)' }}>
                Manual Review
              </span>
            )}
          </div>
          {/* Title */}
          <div className="flex flex-wrap items-center gap-2" style={{ color: 'var(--text-heading)', fontWeight: 600, fontSize: 15 }}>
            {incident.title}
            <ArrowUpRight size={16} style={{ opacity: 0.5 }} />
          </div>
          {/* Tags row */}
          <div className="flex flex-wrap gap-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
              <Repeat size={10} /> {alertCount}x
            </span>
            {durationSec && (
              <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <Clock size={10} /> {formatDuration(durationSec)}
              </span>
            )}
            {unstable && (
              <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(245,158,11,0.25)', color: 'var(--color-accent-amber)' }}>
                <AlertTriangle size={10} /> flapping
              </span>
            )}
            {meta.recommendation?.confidence && (
              <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ background: 'var(--glow-sky)', border: '1px solid rgba(56,189,248,0.2)', color: 'var(--neon-cyan)' }}>
                <GaugeCircle size={10} /> {Math.round(meta.recommendation.confidence * 100)}% AI
              </span>
            )}
            {meta.recommendation?.proposed_action && (
              <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--color-accent-red)' }}>
                <Activity size={10} /> {meta.recommendation.proposed_action}
              </span>
            )}
          </div>
          {/* Operator note */}
          {manualReason && (
            <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              <span style={{ color: 'var(--color-accent-red)', fontWeight: 600 }}>Operator note:</span> {manualReason}
              {manualAt && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>({manualAt})</span>}
            </p>
          )}
        </div>
        <ChevronRight size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
      </div>
    </Link>
  )
}
