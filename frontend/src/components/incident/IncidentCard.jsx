import { Link } from 'react-router-dom'
import {
  Clock,
  ChevronRight,
  Repeat,
  AlertTriangle,
  Activity,
  Flame,
  GaugeCircle,
  Cloud,
} from 'lucide-react'
import StateBadge from '../common/StateBadge'
import SeverityBadge from '../common/SeverityBadge'
import { truncateId, formatTimestamp, formatDuration } from '../../utils/formatters'

const SEVERITY_ACCENTS = {
  CRITICAL: '#f43f5e',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
}

 
function MetricTile({ icon: Icon, label, value, hint, accent }) {
  return (
    <div
      className="rounded-xl px-3 py-2 flex items-center gap-3"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <div
        className="h-8 w-8 rounded-lg flex items-center justify-center"
        style={{ background: `${accent}1a`, color: accent }}
      >
        <Icon size={14} strokeWidth={2} />
      </div>
      <div className="flex-1 min-w-0">
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)' }}>{value}</div>
        {hint && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{hint}</div>
        )}
      </div>
    </div>
  )
}

export default function IncidentCard({ incident }) {
  const totalRetries =
    (incident.investigation_retry_count || 0) +
    (incident.execution_retry_count || 0) +
    (incident.verification_retry_count || 0)

  const meta = incident.meta || {}
  const alertCount = meta._alert_count != null ? Number(meta._alert_count) : 1
  const durationSec = meta._alert_duration_seconds != null ? Number(meta._alert_duration_seconds) : null
  const unstable = Boolean(meta._unstable)
  const confidence = meta.recommendation?.confidence != null ? Math.round(meta.recommendation.confidence * 100) : null
  const accent = SEVERITY_ACCENTS[incident.severity] || '#f97316'
  const summary = meta.INCIDENT_REASON || meta.INCIDENT_DETAILS || incident.title
  const cloud = meta._cloud || meta.cloud
  const tenant = meta._tenant_name || meta.TENANT || meta.tenant
  const manualReason = typeof meta._manual_review_reason === 'string' ? meta._manual_review_reason.trim() : ''
  const manualReview = Boolean(meta._manual_review_required || manualReason)
  const manualAt = meta._manual_review_at ? formatTimestamp(String(meta._manual_review_at)) : null

  return (
    <div
      className="rounded-2xl"
      style={{
        background: `linear-gradient(135deg, ${accent}1f, transparent 70%)`,
        padding: 1,
      }}
    >
      <Link
        to={`/incidents/${incident.id}`}
        className="block h-full rounded-[22px] glass p-5 glass-hover backdrop-blur-md"
        style={{ border: '1px solid rgba(255,255,255,0.05)', position: 'relative' }}
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <button
              type="button"
              onClick={(e) => { e.preventDefault(); navigator.clipboard.writeText(incident.id) }}
              className="cursor-copy inline-flex items-center gap-1"
              style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ display: 'inline-flex', background: accent }}
              />
              {truncateId(incident.id)}
            </button>
            <div className="flex items-center flex-wrap gap-2 mt-2">
              <SeverityBadge severity={incident.severity} />
              <span
                className="rounded-md px-2 py-0.5"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
              >
                {incident.alert_type}
              </span>
              {manualReview && (
                <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5"
                  style={{ fontSize: 11, color: '#f87171', background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.3)' }}>
                  Manual Review
                </span>
              )}
              {cloud && (
                <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <Cloud size={11} />
                  {cloud}
                </span>
              )}
              {tenant && (
                <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5" style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                  tenant · {tenant}
                </span>
              )}
            </div>
          </div>
          <StateBadge state={incident.state} />
        </div>

        <h3
          className="leading-tight"
          style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-heading)' }}
        >
          {incident.title}
        </h3>
        {summary && (
          <p
            className="mt-2 line-clamp-2"
            style={{ fontSize: 13, color: 'var(--text-secondary)' }}
          >
            {summary}
          </p>
        )}

        <div className="grid grid-cols-3 gap-3 mt-4">
          <MetricTile
            icon={Repeat}
            label="Repeats"
            value={`${alertCount}×`}
            hint={unstable ? 'flapping' : 'steady'}
            accent={alertCount > 1 ? '#f59e0b' : accent}
          />
          <MetricTile
            icon={Clock}
            label="Active"
            value={durationSec ? formatDuration(durationSec) : '—'}
            hint={formatTimestamp(incident.created_at)}
            accent="#22d3ee"
          />
          <MetricTile
            icon={Activity}
            label="Retries"
            value={`${totalRetries}/3`}
            hint={totalRetries > 0 ? 'attention' : 'clean run'}
            accent={totalRetries > 0 ? '#f97316' : '#10b981'}
          />
        </div>

        <div className="mt-4 flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {alertCount > 1 && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)' }}
              >
                <Repeat size={10} />
                amplified
              </span>
            )}
            {unstable && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: '#fbbf24', background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.25)' }}
              >
                <AlertTriangle size={10} />
                flapping
              </span>
            )}
            {confidence != null && (
              <span
                className="inline-flex items-center gap-2 rounded-full px-2 py-0.5"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'rgba(8,145,178,0.15)', color: '#38bdf8', border: '1px solid rgba(8,145,178,0.3)' }}
              >
                <GaugeCircle size={10} />
                AI {confidence}%
              </span>
            )}
            {meta.recommendation?.proposed_action && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'rgba(56,189,248,0.08)', color: '#38bdf8', border: '1px solid rgba(56,189,248,0.2)' }}
              >
                <Flame size={10} />
                {meta.recommendation.proposed_action}
              </span>
            )}
            {manualReason && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ fontFamily: 'var(--font-mono)', fontSize: 11, background: 'rgba(248,113,113,0.12)', color: '#f87171', border: '1px solid rgba(248,113,113,0.25)' }}
              >
                Note Saved
              </span>
            )}
          </div>
          <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
        </div>

        {manualReason && (
          <div className="mt-4 rounded-xl px-3 py-2" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#f87171', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Operator note</div>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{manualReason}</p>
            {manualAt && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>Added {manualAt}</div>
            )}
          </div>
        )}
      </Link>
    </div>
  )
}
