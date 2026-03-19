import { useState } from 'react'
import { Sparkles, ShieldCheck, Loader, AlertCircle, CheckCircle2, Info, ShieldAlert } from 'lucide-react'
import { approveIncident } from '../../services/api'
import ConfirmationModal from '../common/ConfirmationModal'
import { extractErrorMessage } from '../../utils/errorHandler'

const RISK_THEME = {
  LOW: { border: 'var(--color-accent-green)', bg: 'rgba(16,185,129,0.06)', text: 'var(--color-accent-green)' },
  MED: { border: 'var(--color-accent-amber)', bg: 'rgba(245,158,11,0.06)', text: 'var(--color-accent-amber)' },
  HIGH: { border: 'var(--color-accent-red)', bg: 'rgba(244,63,94,0.06)', text: 'var(--color-accent-red)' },
}

const APPROVAL_LEVEL_THEME = {
  operator: { label: 'Operator Approval', color: 'var(--neon-indigo)', bg: 'rgba(99,102,241,0.1)', icon: ShieldCheck },
  senior: { label: 'Senior / Admin Approval Required', color: 'var(--color-accent-red)', bg: 'rgba(244,63,94,0.1)', icon: ShieldAlert },
}

export default function AIRecommendationApproval({ incident, ragContext }) {
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [error, setError] = useState(null)
  const [selectedAction, setSelectedAction] = useState(null)

  // Try multiple ways to get recommendation - handle both direct field and meta field
  const recommendation = incident.recommendation || incident.meta?.recommendation || null
  
  // Normalize recommendation structure — preserve all enhanced fields from backend
  const normalizedRecommendation = recommendation && typeof recommendation === 'object' && !Array.isArray(recommendation)
    ? {
        root_cause: recommendation.root_cause || '',
        proposed_action: recommendation.proposed_action || '',
        risk_level: recommendation.risk_level || 'MED',
        confidence: typeof recommendation.confidence === 'number' ? recommendation.confidence : 0.8,
        summary: recommendation.summary || '',
        rationale: recommendation.rationale || '',
        blast_radius: recommendation.blast_radius || '',
        root_cause_category: recommendation.root_cause_category || '',
        contributing_factors: recommendation.contributing_factors || [],
        alternatives: recommendation.alternatives || [],
        verification_criteria: recommendation.verification_criteria || [],
        reasoning_chain: recommendation.reasoning_chain || [],
        evidence_annotations: recommendation.evidence_annotations || {},
      }
    : null

  const manualRequired = Boolean(incident.meta?._manual_review_required)
  const canApprove = incident.state === 'AWAITING_APPROVAL' && Boolean(normalizedRecommendation?.proposed_action)
  const awaitingApproval = incident.state === 'AWAITING_APPROVAL'

  // Approval gate metadata from backend
  const approvalLevel = incident.meta?._approval_level || null
  const approvalReason = incident.meta?._approval_reason || null
  const confidenceMet = incident.meta?._confidence_met !== false
  const seniorRequired = Boolean(incident.meta?._senior_required)
  
  // Always show if there's pattern analysis, recommendation, manual review required, or awaiting approval
  const shouldShow = ragContext || normalizedRecommendation || manualRequired || awaitingApproval
  
  if (!shouldShow) return null

  // Use real alternatives from backend AI recommendation
  const alternativeRecommendations = normalizedRecommendation?.alternatives || []

  // Use selected action or default to primary
  const actionToApprove = selectedAction || normalizedRecommendation?.proposed_action

  async function handleApprove() {
    setModalOpen(false)
    setLoading(true)
    setError(null)
    try {
      const idempotencyKey = `${incident.id}:${actionToApprove}`
      await approveIncident(incident.id, actionToApprove, idempotencyKey)
    } catch (err) {
      setError(extractErrorMessage(err) || err.message)
      setLoading(false)
    }
  }


  const risk = (normalizedRecommendation?.risk_level || 'MED').toUpperCase()
  const theme = RISK_THEME[risk] || RISK_THEME.MED
  const approvalTheme = approvalLevel ? APPROVAL_LEVEL_THEME[approvalLevel] : null

  return (
    <div className="space-y-6" style={{ width: '100%', maxWidth: '100%' }}>
      {/* Recommendations Section */}
      <div className="glass rounded-xl p-5" style={{ borderLeft: `4px solid ${theme.border}`, background: theme.bg }}>
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="flex items-center gap-2" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <Sparkles size={14} style={{ color: 'var(--neon-indigo)' }} />
              AI Recommendation & Approval
            </h3>
            {normalizedRecommendation && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                CONFIDENCE: {(normalizedRecommendation.confidence * 100).toFixed(1)}%
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Senior Approval Badge */}
            {approvalTheme && (
              <span
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md"
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: approvalTheme.color,
                  background: approvalTheme.bg,
                  border: `1px solid ${approvalTheme.color}30`,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                <approvalTheme.icon size={12} />
                {approvalTheme.label}
              </span>
            )}
            <span
              className="px-2.5 py-1 rounded-md"
              style={{ fontSize: 11, fontWeight: 700, color: theme.border, background: 'var(--bg-input)', border: `1px solid ${theme.border}30` }}
            >
              {risk} RISK
            </span>
          </div>
        </div>

        {/* Confidence Gate Info Banner */}
        {approvalLevel && approvalReason && canApprove && (
          <div
            className="mb-4 p-3 rounded-lg flex items-start gap-2"
            style={{
              background: approvalTheme?.bg || 'rgba(59,130,246,0.05)',
              border: `1px solid ${(approvalTheme?.color || 'var(--neon-indigo)')}20`,
            }}
          >
            <Info size={14} style={{ color: approvalTheme?.color || 'var(--neon-indigo)', marginTop: 1, flexShrink: 0 }} />
            <div>
              <p style={{ fontSize: 11, fontWeight: 600, color: approvalTheme?.color || 'var(--neon-indigo)', marginBottom: 2 }}>
                {seniorRequired ? 'Senior/Admin approval required for this action' : 
                 !confidenceMet ? 'Confidence below auto-approval threshold' :
                 'Manual approval required by policy'}
              </p>
              <p style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                {approvalReason}
              </p>
            </div>
          </div>
        )}

        {!normalizedRecommendation ? (
          <div className="space-y-4">
            <div className="p-4 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div className="flex items-start gap-3">
                <AlertCircle size={16} style={{ color: 'var(--color-accent-amber)', marginTop: 2, flexShrink: 0 }} />
                <div className="flex-1">
                  <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>
                    {awaitingApproval ? 'AI Recommendation Pending' : 'No AI Recommendation Available'}
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: ragContext ? 12 : 0 }}>
                    {awaitingApproval 
                      ? 'The AI recommendation service is currently unavailable or the circuit breaker is open. The system is waiting for AI analysis to complete. Please review the pattern analysis above for insights while waiting.'
                      : 'AI analysis is in progress or manual review is required. Check the AI Investigation panel for detailed analysis.'}
                  </p>
                  {ragContext && (
                    <div className="mt-3 p-3 rounded" style={{ background: 'rgba(129,140,248,0.05)', border: '1px solid rgba(129,140,248,0.1)' }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', marginBottom: 2 }}>Pattern Analysis Available:</p>
                      <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        Historical patterns and context have been analyzed. Review the AI Investigation panel above for insights. Based on the patterns detected, you may want to consider manual actions such as investigating the recurring issues or reviewing scheduled jobs.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Primary Recommendation */}
            <div 
              className="p-4 rounded-lg transition-all"
              style={{ 
                background: !selectedAction || selectedAction === normalizedRecommendation.proposed_action ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                border: `2px solid ${!selectedAction || selectedAction === normalizedRecommendation.proposed_action ? 'var(--neon-indigo)' : 'var(--border)'}`,
                cursor: 'pointer'
              }}
              onClick={() => setSelectedAction(normalizedRecommendation.proposed_action)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} style={{ color: 'var(--color-accent-green)' }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)' }}>
                    Primary Recommendation
                  </span>
                  <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-accent-green)', background: 'var(--glow-emerald)' }}>
                    {(normalizedRecommendation.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
                {(!selectedAction || selectedAction === normalizedRecommendation.proposed_action) && (
                  <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: 'var(--neon-indigo)', color: 'white' }}>
                    <CheckCircle2 size={12} />
                  </div>
                )}
              </div>
              <div className="mb-2">
                <div className="p-3 rounded-lg mb-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--neon-indigo)', background: 'var(--terminal-bg)', border: '1px solid rgba(99,102,241,0.1)' }}>
                  <span style={{ color: 'rgba(99,102,241,0.4)', marginRight: 4 }}>$</span>
                  {normalizedRecommendation.proposed_action}
                </div>
                {normalizedRecommendation.summary && (
                  <p style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 8, fontWeight: 500 }}>
                    {normalizedRecommendation.summary}
                  </p>
                )}
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
                  <span style={{ fontWeight: 600 }}>Root cause:</span> {normalizedRecommendation.root_cause}
                </p>
                {normalizedRecommendation.contributing_factors.length > 0 && (
                  <div className="mb-3">
                    <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Contributing factors:</p>
                    <ul className="space-y-1">
                      {normalizedRecommendation.contributing_factors.map((f, i) => (
                        <li key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', paddingLeft: 8 }}>
                          {'\u2022'} {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {normalizedRecommendation.rationale && (
                  <div className="p-3 rounded" style={{ background: 'rgba(129,140,248,0.05)', border: '1px solid rgba(129,140,248,0.1)' }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', marginBottom: 4 }}>Rationale:</p>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {normalizedRecommendation.rationale}
                    </p>
                  </div>
                )}
                {normalizedRecommendation.blast_radius && (
                  <div className="mt-2 flex items-center gap-2">
                    <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Blast radius:</span>
                    <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: theme.border, background: `${theme.border}15`, border: `1px solid ${theme.border}30` }}>
                      {normalizedRecommendation.blast_radius}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Alternative Recommendations from AI */}
            {alternativeRecommendations.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle size={14} style={{ color: 'var(--text-muted)' }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Alternative Options (AI-generated)
                  </span>
                </div>
                <div className="space-y-3">
                  {alternativeRecommendations.map((alt, index) => (
                    <div
                      key={alt.action}
                      className="p-4 rounded-lg transition-all"
                      style={{ 
                        background: selectedAction === alt.action ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                        border: `1px solid ${selectedAction === alt.action ? 'var(--neon-indigo)' : 'var(--border)'}`,
                        cursor: 'pointer'
                      }}
                      onClick={() => setSelectedAction(alt.action)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)' }}>
                            Option {index + 1}
                          </span>
                          <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-accent-amber)', background: 'rgba(245,158,11,0.1)' }}>
                            {(alt.confidence * 100).toFixed(0)}% confidence
                          </span>
                          {alt.risk_level && (
                            <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: (RISK_THEME[alt.risk_level?.toUpperCase()] || RISK_THEME.MED).border, background: (RISK_THEME[alt.risk_level?.toUpperCase()] || RISK_THEME.MED).bg }}>
                              {alt.risk_level} risk
                            </span>
                          )}
                        </div>
                        {selectedAction === alt.action && (
                          <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: 'var(--neon-indigo)', color: 'white' }}>
                            <CheckCircle2 size={12} />
                          </div>
                        )}
                      </div>
                      <div className="mb-2">
                        <div className="p-2 rounded mb-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--neon-indigo)', background: 'var(--terminal-bg)', border: '1px solid rgba(99,102,241,0.1)' }}>
                          <span style={{ color: 'rgba(99,102,241,0.4)', marginRight: 4 }}>$</span>
                          {alt.action}
                        </div>
                        <div className="p-2 rounded" style={{ background: 'rgba(129,140,248,0.03)', border: '1px solid rgba(129,140,248,0.08)' }}>
                          <p style={{ fontSize: 10, fontWeight: 600, color: 'var(--neon-indigo)', marginBottom: 2 }}>Why this option:</p>
                          <p style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                            {alt.rationale}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Approval Controls */}
        {canApprove && (
          <div className="mt-6 pt-6" style={{ borderTop: '1px solid var(--border)' }}>
            {error && (
              <p className="mb-4 px-3 py-2 rounded-md" style={{ fontSize: 12, color: 'var(--color-accent-red)', background: 'var(--glow-rose)' }}>{error}</p>
            )}

            <div className="flex gap-3 flex-wrap items-center">
              <button
                onClick={() => setModalOpen(true)}
                disabled={loading || !actionToApprove}
                className="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
                style={{ background: 'var(--gradient-primary)', boxShadow: '0 4px 12px rgba(99,102,241,0.2)' }}
              >
                {loading ? (
                  <>
                    <Loader size={14} className="animate-spin" /> Processing...
                  </>
                ) : (
                  <>
                    {seniorRequired ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
                    {seniorRequired ? 'Senior Approve & Execute' : 'Approve & Execute'}
                  </>
                )}
              </button>
              {seniorRequired && (
                <span style={{ fontSize: 10, color: 'var(--color-accent-red)', fontWeight: 600 }}>
                  Requires admin role
                </span>
              )}
            </div>
          </div>
        )}

        <ConfirmationModal
          open={modalOpen}
          title={seniorRequired ? 'Senior Approval — Confirm Execution' : 'Confirm Execution'}
          message={
            <div className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <p>You are about to execute <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--neon-indigo)' }}>{actionToApprove}</strong> on this incident.</p>
              {normalizedRecommendation && (!selectedAction || selectedAction === normalizedRecommendation.proposed_action) && (
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  This is the primary recommendation with {(normalizedRecommendation.confidence * 100).toFixed(0)}% confidence.
                </p>
              )}
              {seniorRequired && (
                <p style={{ fontSize: 12, color: 'var(--color-accent-red)', fontWeight: 600 }}>
                  This action requires senior/admin approval and will be audited.
                </p>
              )}
              <p>This action will be logged and cannot be undone.</p>
            </div>
          }
          onConfirm={handleApprove}
          onCancel={() => setModalOpen(false)}
        />

      </div>
    </div>
  )
}
