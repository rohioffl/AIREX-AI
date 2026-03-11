import { useState, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import KeyboardShortcutsModal from '../components/common/KeyboardShortcutsModal'
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
  Ban,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import useIncidentDetail from '../hooks/useIncidentDetail'
import { useTheme } from '../context/ThemeContext'
import StateBadge from '../components/common/StateBadge'
import SeverityBadge from '../components/common/SeverityBadge'
import Terminal from '../components/common/Terminal'
import StatePipeline from '../components/incident/StatePipeline'
import Timeline from '../components/incident/Timeline'
import TimelineChart from '../components/incident/TimelineChart'
import EvidencePanel from '../components/incident/EvidencePanel'
import Site24x7MetricsPanel from '../components/incident/Site24x7MetricsPanel'
import CommentsPanel from '../components/incident/CommentsPanel'
import AssignmentPanel from '../components/incident/AssignmentPanel'
import RelatedIncidentsPanel from '../components/incident/RelatedIncidentsPanel'
import AIAnalysisPanel from '../components/incident/AIAnalysisPanel'
import AIRecommendationApproval from '../components/incident/AIRecommendationApproval'
import ExecutionLogs from '../components/incident/ExecutionLogs'
import VerificationResult from '../components/incident/VerificationResult'
import InvestigationTimeline from '../components/incident/InvestigationTimeline'
import IncidentChat from '../components/incident/IncidentChat'
import ReasoningChain from '../components/incident/ReasoningChain'
import ResolutionOutcome from '../components/incident/ResolutionOutcome'
import AutoRunbook from '../components/incident/AutoRunbook'
import FallbackHistory from '../components/incident/FallbackHistory'
import CorrelationGroup from '../components/incident/CorrelationGroup'
import ConnectionBanner from '../components/common/ConnectionBanner'
import AcknowledgeRejectModal from '../components/incident/AcknowledgeRejectModal'
import { formatTimestamp, formatDuration, formatRelativeTime } from '../utils/formatters'
import { rejectIncident } from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'

const SEVERITY_ACCENT = {
  CRITICAL: '#f43f5e',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
}

const APPROVAL_LEVEL_BADGE = {
  auto: { label: 'Auto-Approved', color: '#10b981', Icon: Zap },
  operator: { label: 'Operator Approval', color: '#3b82f6', Icon: ShieldCheck },
  senior: { label: 'Senior Approval', color: '#f43f5e', Icon: ShieldAlert },
}

export default function IncidentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { incident, loading, error, connected, reconnecting, executionLogs, probeSteps } = useIncidentDetail(id)
  const { isDark } = useTheme()
  const [ackRejectModalOpen, setAckRejectModalOpen] = useState(false)
  const [rejectLoading, setRejectLoading] = useState(false)
  const [rejectError, setRejectError] = useState(null)
  const [showShortcutsModal, setShowShortcutsModal] = useState(false)
  const [approveLoading, setApproveLoading] = useState(false)
  const approveRef = useRef(null)

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onApprove: async () => {
      if (incident?.state === 'AWAITING_APPROVAL' && incident?.meta?.recommendation?.proposed_action) {
        try {
          setApproveLoading(true)
          const { approveIncident } = await import('../services/api')
          const idempotencyKey = `${incident.id}:${incident.meta.recommendation.proposed_action}`
          await approveIncident(incident.id, incident.meta.recommendation.proposed_action, idempotencyKey)
        } catch (err) {
          console.error('Failed to approve:', err)
        } finally {
          setApproveLoading(false)
        }
      }
    },
    onReject: () => {
      if (incident?.state === 'AWAITING_APPROVAL') {
        setAckRejectModalOpen(true)
      }
    },
    onShowHelp: () => setShowShortcutsModal(true),
    onClose: () => {
      setShowShortcutsModal(false)
      setAckRejectModalOpen(false)
    },
    enabled: true,
  })

  const handleReject = async (note) => {
    setRejectLoading(true)
    setRejectError(null)
    try {
      await rejectIncident(incident.id, note)
      navigate('/rejected', { replace: true })
    } catch (err) {
      setRejectError(extractErrorMessage(err) || err.message)
      setRejectLoading(false)
    }
  }

  const handleAcknowledge = () => {
    // Modal will handle opening Gmail
  }

  if (loading) {
    return (
      <div className="space-y-5 animate-fade-in">
        <div className="glass skeleton rounded-xl h-48" />
        <div className="glass skeleton rounded-xl h-16" />
        <div className="grid grid-cols-2 gap-5">
          <div className="glass skeleton rounded-xl h-72" />
          <div className="glass skeleton rounded-xl h-64" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div 
        className="glass rounded-xl p-5" 
        style={{ 
          borderLeft: '4px solid #f43f5e', 
          background: isDark ? 'rgba(244,63,94,0.03)' : '#FFFFFF',
          border: isDark ? 'none' : '1px solid #E5E7EB',
          fontSize: 14, 
          color: '#fb7185' 
        }}
      >
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
  const accent = SEVERITY_ACCENT[incident.severity] || '#f97316'
  const manualReason = typeof meta._manual_review_reason === 'string' ? meta._manual_review_reason.trim() : ''
  const manualAt = meta._manual_review_at ? formatTimestamp(String(meta._manual_review_at)) : null

  // Approval gate metadata
  const approvalLevel = meta._approval_level || null
  const approvalBadge = approvalLevel ? APPROVAL_LEVEL_BADGE[approvalLevel] : null

  return (
    <div className="space-y-6 pb-10 animate-fade-in" style={{ width: '100%', maxWidth: '100%' }}>
      <ConnectionBanner connected={connected} reconnecting={reconnecting} />

      {rejectError && (
        <div
          className="glass rounded-xl p-3"
          style={{
            borderLeft: '3px solid rgba(248,113,113,0.9)',
            background: 'rgba(248,113,113,0.08)',
            fontSize: 12,
            color: '#fb7185',
          }}
        >
          {rejectError}
        </div>
      )}
      {/* Breadcrumb */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2" style={{ fontSize: 14 }}>
          <Link to="/incidents" className="flex items-center gap-1.5 transition-colors" style={{ color: 'var(--text-muted)' }}>
            <ArrowLeft size={14} />
            Incidents
          </Link>
          <span className="opacity-40 transition-opacity hover:opacity-100" style={{ color: 'var(--text-muted)' }}>/</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>{incident.id.substring(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setAckRejectModalOpen(true)
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{
              fontSize: 12,
              fontWeight: 700,
              background: 'rgba(99,102,241,0.1)',
              color: '#818cf8',
              border: '1px solid rgba(99,102,241,0.25)',
            }}
            title="Acknowledge incident"
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(99,102,241,0.15)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(99,102,241,0.1)'}
          >
            <Mail size={13} />
            Acknowledge
          </button>
          <button
            onClick={() => {
              setAckRejectModalOpen(true)
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{
              fontSize: 12,
              fontWeight: 700,
              background: isDark ? 'rgba(248,113,113,0.1)' : '#FFFFFF',
              color: '#f87171',
              border: isDark ? '1px solid rgba(248,113,113,0.25)' : '1px solid #E5E7EB',
            }}
            title="Reject incident"
            onMouseEnter={(e) => e.currentTarget.style.background = isDark ? 'rgba(248,113,113,0.15)' : '#F9FAFB'}
            onMouseLeave={(e) => e.currentTarget.style.background = isDark ? 'rgba(248,113,113,0.1)' : '#FFFFFF'}
          >
            <Ban size={13} />
            Reject
          </button>
          <div
            className="flex items-center gap-2 px-3 py-1 rounded-full"
            style={{
              fontSize: 11,
              fontWeight: 700,
              border: isDark 
                ? `1px solid ${connected ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'}`
                : `1px solid ${connected ? '#D1FAE5' : '#FEE2E2'}`,
              background: isDark 
                ? (connected ? 'rgba(16,185,129,0.05)' : 'rgba(244,63,94,0.05)')
                : (connected ? '#ECFDF5' : '#FEF2F2'),
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
        style={{ 
          border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(220,38,38,0.25)', 
          background: isDark ? 'transparent' : '#FFFFFF',
          boxShadow: isDark ? 'none' : '0 1px 2px rgba(0,0,0,0.04)',
          width: '100%', 
          maxWidth: '100%', 
          boxSizing: 'border-box' 
        }}
      >
        {!isDark && (
          <div
            className="absolute left-0 top-0 bottom-0"
            style={{
              width: '4px',
              background: '#DC2626',
              borderRadius: '4px 0 0 4px',
            }}
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
                  {/* Approval Level Badge */}
                  {approvalBadge && (
                    <div
                      className="mt-3 flex items-center gap-1.5 px-2 py-1 rounded-md"
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: approvalBadge.color,
                        background: `${approvalBadge.color}15`,
                        border: `1px solid ${approvalBadge.color}30`,
                      }}
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

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: 'Alert Repeats', value: `${alertCount}×`, hint: lastSeen ? `last ${lastSeen}` : 'single alert', icon: Repeat },
              { label: 'Active Duration', value: durationSec ? formatDuration(durationSec) : '—', hint: firstSeen ? `since ${firstSeen}` : 'waiting data', icon: Clock },
              { label: 'Cloud Target', value: cloud ? cloud.toUpperCase() : 'Unknown', hint: region || 'no region received', icon: Cloud },
              { label: 'Tenant Scope', value: tenant || 'default', hint: `state ${incident.state}`, icon: GaugeCircle },
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

          {latestTransition && (
            <div 
              className="glass rounded-xl p-4" 
              style={{ 
                borderLeft: `3px solid ${incident.state === 'REJECTED' ? '#f87171' : '#22d3ee'}`,
                background: isDark 
                  ? (incident.state === 'REJECTED' ? 'rgba(248,113,113,0.08)' : 'rgba(34,211,238,0.08)')
                  : '#F8FAFC',
                border: isDark ? 'none' : '1px solid #E2E8F0',
              }}
            >
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
            <div 
              className="glass rounded-xl p-4" 
              style={{ 
                borderLeft: '3px solid rgba(248,113,113,0.6)', 
                background: isDark ? 'rgba(248,113,113,0.08)' : '#F8FAFC',
                border: isDark ? 'none' : '1px solid #E2E8F0',
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: '#f87171', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Operator note</div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>{manualReason}</p>
              {manualAt && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Noted {manualAt}</div>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Pipeline */}
      <div className="glass rounded-xl px-4 py-2" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box', overflowX: 'auto' }}>
        <StatePipeline currentState={incident.state} />
      </div>

      {/* Vertical Flow Layout */}
      <div className="space-y-6" style={{ width: '100%', maxWidth: '100%' }}>
        {/* 0. Same server — other alerts (Top of flow) */}
        {incident.related_incidents && incident.related_incidents.length > 0 && incident.host_key && (
          <div
            className="glass rounded-xl p-4 transition-all"
            style={{
              borderLeft: '3px solid rgba(99,102,241,0.4)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderLeftColor = 'rgba(99,102,241,0.8)'
              e.currentTarget.style.background = 'rgba(99,102,241,0.05)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderLeftColor = 'rgba(99,102,241,0.4)'
              e.currentTarget.style.background = ''
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                <Server size={12} />
                Same server — other alerts
              </div>
              <Link
                to={`/alerts?host=${encodeURIComponent(incident.host_key)}`}
                className="flex items-center gap-1 transition-colors"
                style={{ fontSize: 10, fontWeight: 600, color: '#818cf8', textDecoration: 'none' }}
                onMouseEnter={(e) => e.currentTarget.style.color = '#a5b4fc'}
                onMouseLeave={(e) => e.currentTarget.style.color = '#818cf8'}
              >
                View all ({incident.related_incidents.length})
                <ChevronRight size={12} />
              </Link>
            </div>
            <ul className="space-y-2">
              {incident.related_incidents
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
                .slice(0, 3)
                .map((rel) => (
                  <li key={rel.id}>
                    <div
                      onClick={(e) => {
                        e.preventDefault()
                        navigate(`/incidents/${rel.id}`)
                      }}
                      className="flex items-center justify-between gap-2 py-2 px-3 rounded-lg transition-colors cursor-pointer"
                      style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: 13 }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(99,102,241,0.1)'
                        e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'var(--bg-input)'
                        e.currentTarget.style.borderColor = 'var(--border)'
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="truncate" style={{ fontSize: 13, fontWeight: 500 }}>{rel.title}</div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                          {formatRelativeTime(rel.created_at)}
                        </div>
                      </div>
                      <span className="flex items-center gap-2 flex-shrink-0">
                        <StateBadge state={rel.state} />
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>{rel.alert_type}</span>
                        <ChevronRight size={14} style={{ color: '#818cf8' }} />
                      </span>
                    </div>
                  </li>
                ))}
            </ul>
          </div>
        )}
        {/* 0.5 Investigation Timeline (live probe progress) */}
        <InvestigationTimeline probeSteps={probeSteps} />

        {/* 0.7 Cross-Host Correlation (Phase 4 ARE) */}
        <CorrelationGroup incident={incident} />

        {/* 1. AI Investigation */}
        <AIAnalysisPanel incident={incident} />

        {/* 2. Evidence */}
        <EvidencePanel evidence={incident.evidence} incident={incident} />

        {/* 2.5. Site24x7 Metrics (if available) */}
        {incident?.meta?._source === 'site24x7' && (
          <Site24x7MetricsPanel incident={incident} />
        )}

        {/* 3. AI Recommendation & Approval */}
        <div style={{ width: '100%', maxWidth: '100%' }}>
          <div className="flex items-center gap-2 mb-3">
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>AI Recommendation & Approval</span>
          </div>
          <AIRecommendationApproval incident={incident} ragContext={incident.rag_context} />
          <ReasoningChain
            reasoningChain={meta.recommendation?.reasoning_chain}
            verificationCriteria={meta.recommendation?.verification_criteria}
          />
        </div>

        {/* 4. AI Chat */}
        <IncidentChat incidentId={id} />

        {/* 4.5 Fallback History (Phase 3 ARE) */}
        <FallbackHistory incident={incident} />

        {/* 4.6 Resolution Outcome & Feedback */}
        <ResolutionOutcome incident={incident} />

        {/* 4.7 Auto-Generated Runbook (Phase 5 ARE) */}
        <AutoRunbook incident={incident} />

        {/* 5. Assignment */}
        <AssignmentPanel incident={incident} />

        {/* 6. Related Incidents (Manual Links) */}
        <RelatedIncidentsPanel incident={incident} />

        {/* 7. Comments & Collaboration */}
        <CommentsPanel incident={incident} />

        {/* Additional Info Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
          <VerificationResult state={incident.state} incident={incident} />
          <div className="space-y-6">
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
      </div>

      {/* Timeline */}
      <div className="space-y-6">
        <div className="glass rounded-xl p-6" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
          <span className="block mb-6 neon-text-cyan" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Timeline</span>
          <Timeline transitions={incident.state_transitions} />
        </div>
        {incident.state_transitions && incident.state_transitions.length > 0 && (
          <TimelineChart
            transitions={incident.state_transitions}
            incidentCreatedAt={incident.created_at}
            incidentResolvedAt={incident.state === 'RESOLVED' ? incident.updated_at : null}
          />
        )}
      </div>

      {/* Acknowledge/Reject Modal */}
      <AcknowledgeRejectModal
        open={ackRejectModalOpen}
        incident={incident}
        onAcknowledge={handleAcknowledge}
        onReject={handleReject}
        onCancel={() => {
          setAckRejectModalOpen(false)
          setRejectError(null)
        }}
        loading={rejectLoading}
      />

      {/* Keyboard Shortcuts Modal */}
      {showShortcutsModal && (
        <KeyboardShortcutsModal onClose={() => setShowShortcutsModal(false)} />
      )}
    </div>
  )
}
