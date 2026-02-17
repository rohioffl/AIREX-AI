import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Radio, WifiOff, Mail, Server, ChevronRight } from 'lucide-react'
import useIncidentDetail from '../hooks/useIncidentDetail'
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
import { formatTimestamp, buildAcknowledgeMailto } from '../utils/formatters'

export default function IncidentDetail() {
  const { id } = useParams()
  const { incident, loading, error, connected, reconnecting, executionLogs } = useIncidentDetail(id)

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
      <header className="glass rounded-xl p-6 relative overflow-hidden" style={{ borderTop: '2px solid rgba(99,102,241,0.4)' }}>
        <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full pointer-events-none" style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.04) 0%, transparent 70%)' }} />
        <div className="relative flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-3">
              <SeverityBadge severity={incident.severity} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{incident.alert_type}</span>
            </div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              {incident.title}
            </h1>
            <div className="flex flex-wrap gap-x-6 gap-y-1 mt-4" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              <span>CREATED <span style={{ color: 'var(--text-secondary)' }}>{formatTimestamp(incident.created_at)}</span></span>
              <span>UPDATED <span style={{ color: 'var(--text-secondary)' }}>{formatTimestamp(incident.updated_at)}</span></span>
            </div>
          </div>
          <StateBadge state={incident.state} />
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
          <RecommendationCard recommendation={incident.recommendation} state={incident.state} />
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
