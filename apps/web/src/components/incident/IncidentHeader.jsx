import {
  Repeat,
  Clock,
  Cloud,
  GaugeCircle,
  AlertTriangle,
  Activity,
  MapPin,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import StateBadge from '../common/StateBadge'
import SeverityBadge from '../common/SeverityBadge'
import { formatTimestamp, formatDuration } from '../../utils/formatters'

const SEVERITY_ACCENT = {
  CRITICAL: 'var(--color-accent-red)',
  HIGH: 'var(--brand-orange)',
  MEDIUM: 'var(--color-accent-amber)',
  LOW: 'var(--color-accent-green)',
}

const APPROVAL_LEVEL_BADGE = {
  operator: { label: 'Operator Approval', color: 'var(--neon-cyan)', Icon: ShieldCheck },
  senior: { label: 'Senior Approval', color: 'var(--color-accent-red)', Icon: ShieldAlert },
}

export default function IncidentHeader({ incident }) {
  const { isDark } = useTheme()
  const meta = incident.meta || {}
  const alertCount = meta._alert_count != null ? Number(meta._alert_count) : 1
  const durationSec = meta._alert_duration_seconds != null ? Number(meta._alert_duration_seconds) : null
  const firstSeen = meta._alert_first_seen_at ? formatTimestamp(String(meta._alert_first_seen_at)) : null
  const lastSeen = meta._alert_last_seen_at ? formatTimestamp(String(meta._alert_last_seen_at)) : null
  const unstable = Boolean(meta._unstable)
  const cloud = meta._cloud || meta.cloud
  const region = meta._region || meta.region || meta.zone || meta._zone
  const tenant = meta._tenant_name || meta.tenant
  const summary = meta.INCIDENT_REASON || meta.INCIDENT_DETAILS
  const latestTransition = incident.state_transitions?.[incident.state_transitions.length - 1]
  const confidence = meta.recommendation?.confidence != null ? Math.round(meta.recommendation.confidence * 100) : null
  const accent = SEVERITY_ACCENT[incident.severity] || 'var(--brand-orange)'
  const manualReason = typeof meta._manual_review_reason === 'string' ? meta._manual_review_reason.trim() : ''
  const manualAt = meta._manual_review_at ? formatTimestamp(String(meta._manual_review_at)) : null
  const approvalLevel = meta._approval_level || null
  const approvalBadge = approvalLevel ? APPROVAL_LEVEL_BADGE[approvalLevel] : null

  return (
    <header
      className="rounded-2xl border relative overflow-hidden"
      style={{
        border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(220,38,38,0.25)',
        background: isDark ? 'transparent' : '#FFFFFF',
        boxShadow: isDark ? 'none' : '0 1px 2px rgba(0,0,0,0.04)',
        width: '100%',
        maxWidth: '100%',
        boxSizing: 'border-box',
      }}
    >
      {!isDark && (
        <div
          className="absolute left-0 top-0 bottom-0"
          style={{ width: '4px', background: accent, borderRadius: '4px 0 0 4px' }}
        />
      )}
      <div
        className="absolute inset-0"
        style={{
          background: isDark
            ? `radial-gradient(circle at 20% 20%, ${accent}55, transparent 65%), linear-gradient(135deg, rgba(11,12,16,0.95), rgba(16,18,24,0.95))`
            : 'transparent',
        }}
      />
      <div className="relative p-6 flex flex-col gap-6">
        {/* Title row */}
        <div className="flex flex-col lg:flex-row lg:items-start gap-6">
          <div className="flex-1 min-w-0 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={incident.severity} />
              <StateBadge state={incident.state} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {incident.alert_type}
              </span>
              {cloud && (
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--neon-cyan)', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.3)' }}>
                  <Cloud size={11} />{cloud}
                </span>
              )}
              {tenant && (
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)' }}>
                  workspace · {tenant}
                </span>
              )}
              {region && (
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--neon-cyan)', background: 'rgba(8,145,178,0.15)', border: '1px solid rgba(8,145,178,0.3)' }}>
                  <MapPin size={11} />{region}
                </span>
              )}
              {unstable && (
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--color-accent-amber)', background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(245,158,11,0.25)' }}>
                  <AlertTriangle size={11} />flapping
                </span>
              )}
            </div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              {incident.title}
            </h1>
            {summary && <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{summary}</p>}
            <div className="flex flex-wrap gap-4" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              <span>CREATED <span style={{ color: 'var(--text-secondary)' }}>{formatTimestamp(incident.created_at)}</span></span>
              <span>UPDATED <span style={{ color: 'var(--text-secondary)' }}>{formatTimestamp(incident.updated_at)}</span></span>
            </div>
          </div>

          {/* Sidebar cards */}
          <div className="w-full lg:w-60 flex flex-col gap-3">
            {confidence != null && (
              <div className="rounded-2xl p-4" style={{ background: isDark ? 'rgba(15,23,42,0.6)' : 'rgba(255,255,255,0.6)', border: '1px solid rgba(59,130,246,0.3)' }}>
                <div className="flex items-center justify-between text-xs" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  <span>AI Confidence</span>
                  <span>{confidence}%</span>
                </div>
                <div className="mt-2 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(148,163,184,0.2)' }}>
                  <div className="h-full" style={{ width: `${confidence}%`, background: accent }} />
                </div>
                {meta.recommendation?.proposed_action && (
                  <div className="mt-3 text-sm" style={{ color: 'var(--text-heading)', fontWeight: 600 }}>
                    <Activity size={14} style={{ marginRight: 4, display: 'inline-block' }} />
                    {meta.recommendation.proposed_action}
                  </div>
                )}
                {approvalBadge && (
                  <div
                    className="mt-3 flex items-center gap-1.5 px-2 py-1 rounded-md"
                    style={{ fontSize: 10, fontWeight: 700, color: approvalBadge.color, background: `${approvalBadge.color}15`, border: `1px solid ${approvalBadge.color}30` }}
                  >
                    <approvalBadge.Icon size={11} />
                    {approvalBadge.label}
                  </div>
                )}
              </div>
            )}
            <div className="rounded-2xl p-4" style={{ background: isDark ? 'rgba(15,23,42,0.6)' : 'rgba(255,255,255,0.6)', border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.08)' }}>
              <div className="text-xs" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Alert Digest</div>
              <div className="mt-3 space-y-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                <div className="flex items-center justify-between"><span>Repeats</span><span>{alertCount}×</span></div>
                <div className="flex items-center justify-between"><span>Duration</span><span>{durationSec ? formatDuration(durationSec) : '—'}</span></div>
                <div className="flex items-center justify-between"><span>First seen</span><span>{firstSeen || '—'}</span></div>
                <div className="flex items-center justify-between"><span>Last seen</span><span>{lastSeen || '—'}</span></div>
              </div>
            </div>
          </div>
        </div>

        {/* Metric cards row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'Alert Repeats', value: `${alertCount}×`, hint: lastSeen ? `last ${lastSeen}` : 'single alert', icon: Repeat },
            { label: 'Active Duration', value: durationSec ? formatDuration(durationSec) : '—', hint: firstSeen ? `since ${firstSeen}` : 'waiting data', icon: Clock },
            { label: 'Cloud Target', value: cloud ? cloud.toUpperCase() : 'Unknown', hint: region || 'no region received', icon: Cloud },
            { label: 'Workspace Scope', value: tenant || 'default', hint: `state ${incident.state}`, icon: GaugeCircle },
          ].map((card) => (
            <div key={card.label} className="rounded-2xl px-4 py-3 hover-lift" style={{ background: isDark ? 'rgba(6,8,15,0.6)' : 'rgba(255,255,255,0.6)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.08)' }}>
              <div className="flex items-center justify-between" style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {card.label}
                <card.icon size={13} />
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{card.value}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{card.hint}</div>
            </div>
          ))}
        </div>

        {/* Last action banner */}
        {latestTransition && (
          <div
            className="glass rounded-xl p-4"
            style={{
              borderLeft: `3px solid ${incident.state === 'REJECTED' ? 'var(--color-accent-red)' : 'var(--neon-cyan)'}`,
              background: isDark
                ? (incident.state === 'REJECTED' ? 'rgba(248,113,113,0.08)' : 'rgba(34,211,238,0.08)')
                : '#F8FAFC',
              border: isDark ? 'none' : '1px solid #E2E8F0',
            }}
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Last Action</span>
                <div style={{ fontSize: 16, fontWeight: 700, color: incident.state === 'REJECTED' ? 'var(--color-accent-red)' : 'var(--text-heading)' }}>
                  {latestTransition.to_state === 'REJECTED' ? 'Manually rejected' : `Moved to ${latestTransition.to_state}`}
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{latestTransition.reason || 'No reason provided'}</p>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                {formatTimestamp(latestTransition.created_at)}
              </div>
            </div>
          </div>
        )}

        {/* Operator note */}
        {manualReason && (
          <div
            className="glass rounded-xl p-4"
            style={{
              borderLeft: '3px solid rgba(248,113,113,0.6)',
              background: isDark ? 'rgba(248,113,113,0.08)' : '#F8FAFC',
              border: isDark ? 'none' : '1px solid #E2E8F0',
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-accent-red)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Operator note</div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>{manualReason}</p>
            {manualAt && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Noted {manualAt}</div>}
          </div>
        )}
      </div>
    </header>
  )
}
