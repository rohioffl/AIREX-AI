import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Radio,
  WifiOff,
  Mail,
  Server,
  ChevronRight,
  Repeat,
  Clock,
  AlertTriangle,
  GaugeCircle,
  Activity,
  Cloud,
  MapPin,
} from 'lucide-react'
import useIncidentDetail from '../hooks/useIncidentDetail'
import { useTheme } from '../context/ThemeContext'
import StateBadge from '../components/common/StateBadge'
import SeverityBadge from '../components/common/SeverityBadge'
import Terminal from '../components/common/Terminal'
import StatePipeline from '../components/incident/StatePipeline'
import Timeline from '../components/incident/Timeline'
import EvidencePanel from '../components/incident/EvidencePanel'
import RecommendationCard from '../components/incident/RecommendationCard'
import ApprovalControls from '../components/incident/ApprovalControls'
import ExecutionLogs from '../components/incident/ExecutionLogs'
import VerificationResult from '../components/incident/VerificationResult'
import ConnectionBanner from '../components/common/ConnectionBanner'
import { formatTimestamp, buildAcknowledgeMailto, formatDuration } from '../utils/formatters'

const SEVERITY_ACCENT = {
  CRITICAL: '#f43f5e',
  HIGH: '#fb923c',
  MEDIUM: '#22d3ee',
  LOW: '#10b981',
}

export default function IncidentDetail() {
  const { id } = useParams()
  const { incident, loading, error, connected, reconnecting, executionLogs } = useIncidentDetail(id)
  const { isDark } = useTheme()

  if (loading) {
    return (
      <div className="space-y-5 animate-fade-in">
        <div className="glass rounded-xl h-40 shimmer" />
        <div className="glass rounded-xl h-12 shimmer" />
        <div className="grid grid-cols-2 gap-5">
          <div className="glass rounded-xl h-64 shimmer" />
          <div className="glass rounded-xl h-64 shimmer" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass rounded-xl p-5" style={{ borderLeft: '4px solid #f43f5e', background: 'rgba(244,63,94,0.03)', fontSize: 14, color: '#fb7185' }}>
        {error}
      </div>
    )
  }

  if (!incident) {
    return <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>Incident not found.</p>
  }

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
  const accent = SEVERITY_ACCENT[incident.severity] || '#6366f1'
  const manualReason = typeof meta._manual_review_reason === 'string' ? meta._manual_review_reason.trim() : ''
  const manualAt = meta._manual_review_at ? formatTimestamp(String(meta._manual_review_at)) : null

  return (
    <div className="space-y-6 pb-10 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} />
      {/* Breadcrumb */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2" style={{ fontSize: 14 }}>
          <Link to="/incidents" className="flex items-center gap-1.5 transition-colors" style={{ color: 'var(--text-muted)' }}>
            <ArrowLeft size={14} />
            Incidents
          </Link>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>{incident.id.substring(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={buildAcknowledgeMailto(incident, { escalationEmail: incident.meta?._escalation_email || '' })}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{
              fontSize: 12,
              fontWeight: 700,
              background: 'rgba(99,102,241,0.1)',
              color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.25)',
            }}
            title="Acknowledge — opens Gmail with incident details"
          >
            <Mail size={13} />
            Acknowledge
          </a>
          <div
            className="flex items-center gap-2 px-3 py-1 rounded-full"
            style={{
              fontSize: 11,
              fontWeight: 700,
              border: `1px solid ${connected ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'}`,
              background: connected ? 'rgba(16,185,129,0.05)' : 'rgba(244,63,94,0.05)',
              color: connected ? '#34d399' : '#fb7185',
            }}
          >
            {connected ? <Radio size={12} /> : <WifiOff size={12} />}
            {connected ? 'LIVE' : 'OFFLINE'}
          </div>
        </div>
      </div>

      {/* Header */}
      <header
        className="rounded-2xl border relative overflow-hidden"
        style={{ borderColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)' }}
      >
        <div
          className="absolute inset-0"
          style={{
            background: isDark
              ? `radial-gradient(circle at 20% 20%, ${accent}33, transparent 55%), linear-gradient(135deg, rgba(15,21,37,0.95), rgba(6,8,15,0.95))`
              : `radial-gradient(circle at 20% 20%, ${accent}22, transparent 55%), linear-gradient(135deg, rgba(255,255,255,0.95), rgba(241,245,249,0.95))`,
          }}
        />
        <div className="relative p-6 flex flex-col gap-6">
          <div className="flex flex-col lg:flex-row lg:items-start gap-6">
            <div className="flex-1 min-w-0 space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={incident.severity} />
                <StateBadge state={incident.state} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{incident.alert_type}</span>
                {cloud && (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: '#93c5fd', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.3)' }}>
                    <Cloud size={11} />
                    {cloud}
                  </span>
                )}
                {tenant && (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)' }}>
                    tenant · {tenant}
                  </span>
                )}
                {region && (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: '#f8fafc', background: 'rgba(8,145,178,0.15)', border: '1px solid rgba(8,145,178,0.3)' }}>
                    <MapPin size={11} />
                    {region}
                  </span>
                )}
                {unstable && (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: '#fbbf24', background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.25)' }}>
                    <AlertTriangle size={11} />
                    flapping
                  </span>
                )}
              </div>
              <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                {incident.title}
              </h1>
              {summary && (
                <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{summary}</p>
              )}
              <div className="flex flex-wrap gap-4" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                <span>CREATED <span style={{ color: 'var(--text-secondary)' }}>{formatTimestamp(incident.created_at)}</span></span>
                <span>UPDATED <span style={{ color: 'var(--text-secondary)' }}>{formatTimestamp(incident.updated_at)}</span></span>
              </div>
            </div>
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

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: 'Alert Repeats', value: `${alertCount}×`, hint: lastSeen ? `last ${lastSeen}` : 'single alert', icon: Repeat },
              { label: 'Active Duration', value: durationSec ? formatDuration(durationSec) : '—', hint: firstSeen ? `since ${firstSeen}` : 'waiting data', icon: Clock },
              { label: 'Cloud Target', value: cloud ? cloud.toUpperCase() : 'Unknown', hint: region || 'no region received', icon: Cloud },
              { label: 'Tenant Scope', value: tenant || 'default', hint: `state ${incident.state}`, icon: GaugeCircle },
            ].map((card) => (
              <div key={card.label} className="rounded-2xl px-4 py-3" style={{ background: isDark ? 'rgba(6,8,15,0.6)' : 'rgba(255,255,255,0.6)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.08)' }}>
                <div className="flex items-center justify-between" style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {card.label}
                  <card.icon size={13} />
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{card.value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{card.hint}</div>
              </div>
            ))}
          </div>

          {latestTransition && (
            <div className="glass rounded-xl p-4" style={{ borderLeft: `3px solid ${incident.state === 'REJECTED' ? '#f87171' : '#22d3ee'}`, background: incident.state === 'REJECTED' ? 'rgba(248,113,113,0.08)' : 'rgba(34,211,238,0.08)' }}>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Last Action</span>
                  <div style={{ fontSize: 16, fontWeight: 700, color: incident.state === 'REJECTED' ? '#f87171' : 'var(--text-heading)' }}>
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

          {manualReason && (
            <div className="glass rounded-xl p-4" style={{ borderLeft: '3px solid rgba(248,113,113,0.6)', background: 'rgba(248,113,113,0.08)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#f87171', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Operator note</div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>{manualReason}</p>
              {manualAt && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Noted {manualAt}</div>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Related incidents (same server) */}
      {incident.related_incidents?.length > 0 && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '3px solid rgba(99,102,241,0.4)' }}>
          <div className="flex items-center gap-2 mb-3" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            <Server size={12} />
            Same server — other alerts
          </div>
          <ul className="space-y-2">
            {incident.related_incidents.map((rel) => (
              <li key={rel.id}>
                <Link
                  to={`/incidents/${rel.id}`}
                  className="flex items-center justify-between gap-2 py-2 px-3 rounded-lg transition-colors"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: 13 }}
                >
                  <span className="truncate">{rel.title}</span>
                  <span className="flex items-center gap-1 flex-shrink-0">
                    <StateBadge state={rel.state} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{rel.alert_type}</span>
                    <ChevronRight size={14} style={{ color: '#818cf8' }} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Pipeline */}
      <div className="glass rounded-xl px-4 py-2">
        <StatePipeline currentState={incident.state} />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        <div className="space-y-6">
          <RecommendationCard recommendation={incident.recommendation} state={incident.state} ragContext={incident.rag_context} />
          <EvidencePanel evidence={incident.evidence} />
        </div>
        <div className="space-y-6">
          <ApprovalControls incident={incident} />
          <VerificationResult state={incident.state} />
          <ExecutionLogs executions={incident.executions} state={incident.state} liveLogs={executionLogs} />
          {/* Diagnostics Terminal */}
          {incident.meta?.diagnostics && (
            <div>
              <span className="block mb-2" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Diagnostics</span>
              <Terminal content={incident.meta.diagnostics} hostname={incident.alert_type || 'server'} />
            </div>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="glass rounded-xl p-6">
        <span className="block mb-6" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Timeline</span>
        <Timeline transitions={incident.state_transitions} />
      </div>
    </div>
  )
}
