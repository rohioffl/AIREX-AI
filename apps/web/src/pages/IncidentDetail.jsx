import { useEffect, useState } from 'react'
import { useParams, Link, useLocation, useNavigate } from 'react-router-dom'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import KeyboardShortcutsModal from '../components/common/KeyboardShortcutsModal'
import {
  ArrowLeft,
  Radio,
  WifiOff,
  Mail,
  Server,
  ChevronRight,
  Ban,
} from 'lucide-react'
import useIncidentDetail from '../hooks/useIncidentDetail'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import Terminal from '../components/common/Terminal'
import IncidentHeader from '../components/incident/IncidentHeader'
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
import StateBadge from '../components/common/StateBadge'
import AcknowledgeRejectModal from '../components/incident/AcknowledgeRejectModal'
import { formatRelativeTime } from '../utils/formatters'
import { rejectIncident } from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'


export default function IncidentDetail() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const tenantOverride = new URLSearchParams(location.search).get('tenant_id')
  const { activeTenant, switchTenant } = useAuth()
  const { incident, loading, error, connected, reconnecting, executionLogs, probeSteps } = useIncidentDetail(id, tenantOverride)
  const { isDark } = useTheme()
  const [ackRejectModalOpen, setAckRejectModalOpen] = useState(false)
  const [modalInitialAction, setModalInitialAction] = useState(null) // 'acknowledge' | 'reject'
  const [rejectLoading, setRejectLoading] = useState(false)
  const [rejectError, setRejectError] = useState(null)
  const [showShortcutsModal, setShowShortcutsModal] = useState(false)
  const [, setApproveLoading] = useState(false)

  useEffect(() => {
    if (!tenantOverride) return
    if (String(activeTenant?.id || '') === String(tenantOverride)) return
    switchTenant(tenantOverride).catch((err) => {
      console.warn('Failed to switch tenant for incident detail view:', err)
    })
  }, [activeTenant?.id, switchTenant, tenantOverride])

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
        setModalInitialAction('reject')
        setAckRejectModalOpen(true)
      }
    },
    onShowHelp: () => setShowShortcutsModal(true),
    onClose: () => {
      setShowShortcutsModal(false)
      setAckRejectModalOpen(false)
      setModalInitialAction(null)
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
          borderLeft: '4px solid var(--color-accent-red)', 
          background: isDark ? 'rgba(244,63,94,0.03)' : '#FFFFFF',
          border: isDark ? 'none' : '1px solid #E5E7EB',
          fontSize: 14, 
          color: 'var(--color-accent-red)' 
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
            color: 'var(--color-accent-red)',
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
              setModalInitialAction('acknowledge')
              setAckRejectModalOpen(true)
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{
              fontSize: 12,
              fontWeight: 700,
              background: 'var(--glow-indigo)',
              color: 'var(--neon-indigo)',
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
              setModalInitialAction('reject')
              setAckRejectModalOpen(true)
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{
              fontSize: 12,
              fontWeight: 700,
              background: isDark ? 'rgba(248,113,113,0.1)' : '#FFFFFF',
              color: 'var(--color-accent-red)',
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
              color: connected ? 'var(--neon-green)' : 'var(--color-accent-red)',
            }}
          >
            {connected ? <Radio size={12} /> : <WifiOff size={12} />}
            {connected ? 'LIVE' : 'OFFLINE'}
          </div>
        </div>
      </div>

      {/* Header */}
      <IncidentHeader incident={incident} />

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
                style={{ fontSize: 10, fontWeight: 600, color: 'var(--neon-indigo)', textDecoration: 'none' }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--neon-indigo)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--neon-indigo)'}
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
                        <ChevronRight size={14} style={{ color: 'var(--neon-indigo)' }} />
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
        initialAction={modalInitialAction}
        onAcknowledge={handleAcknowledge}
        onReject={handleReject}
        onCancel={() => {
          setAckRejectModalOpen(false)
          setModalInitialAction(null)
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
