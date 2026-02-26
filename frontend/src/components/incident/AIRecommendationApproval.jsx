import { useState } from 'react'
import { Sparkles, ShieldCheck, Loader, AlertCircle, CheckCircle2, XCircle, Info } from 'lucide-react'
import { approveIncident } from '../../services/api'
import ConfirmationModal from '../common/ConfirmationModal'
import { extractErrorMessage } from '../../utils/errorHandler'

const RISK_THEME = {
  LOW: { border: '#10b981', bg: 'rgba(16,185,129,0.06)', text: '#10b981' },
  MED: { border: '#f59e0b', bg: 'rgba(245,158,11,0.06)', text: '#f59e0b' },
  HIGH: { border: '#f43f5e', bg: 'rgba(244,63,94,0.06)', text: '#f43f5e' },
}

// Action descriptions and alternatives
const ACTION_INFO = {
  restart_service: {
    name: 'Restart Service',
    description: 'Gracefully restart the affected service to clear resource issues and restore normal operation.',
    alternatives: ['scale_instances', 'kill_process'],
    rationale: 'This action is recommended when the service is consuming excessive resources or has become unresponsive. A restart will clear memory leaks and reset the service state.',
  },
  clear_logs: {
    name: 'Clear Log Files',
    description: 'Remove old log files to free up disk space and prevent further disk-related issues.',
    alternatives: ['resize_disk'],
    rationale: 'Log files are consuming significant disk space. Clearing them will free up storage without affecting service functionality.',
  },
  scale_instances: {
    name: 'Scale Instances',
    description: 'Increase the number of running instances to handle increased load and distribute traffic.',
    alternatives: ['restart_service'],
    rationale: 'Current capacity is insufficient for the load. Scaling out will improve performance and reduce per-instance load.',
  },
  kill_process: {
    name: 'Kill Process',
    description: 'Terminate a specific runaway process that is consuming excessive resources.',
    alternatives: ['restart_service'],
    rationale: 'A specific process is causing resource exhaustion. Terminating it will free resources without affecting the entire service.',
  },
  flush_cache: {
    name: 'Flush Cache',
    description: 'Clear cache entries to free memory and resolve cache-related performance issues.',
    alternatives: ['restart_service'],
    rationale: 'Cache is consuming excessive memory or contains stale data. Flushing will free memory and force fresh data retrieval.',
  },
  rotate_credentials: {
    name: 'Rotate Credentials',
    description: 'Generate new authentication credentials to replace compromised or expired ones.',
    alternatives: [],
    rationale: 'Credentials have been compromised or are expiring soon. Rotation is required for security.',
  },
  rollback_deployment: {
    name: 'Rollback Deployment',
    description: 'Revert to the previous deployment version to restore service stability.',
    alternatives: ['restart_service'],
    rationale: 'The current deployment is causing issues. Rolling back will restore the previous stable version.',
  },
  resize_disk: {
    name: 'Resize Disk',
    description: 'Increase disk capacity to accommodate growing storage needs.',
    alternatives: ['clear_logs'],
    rationale: 'Disk space is insufficient for current operations. Resizing will provide additional capacity.',
  },
  drain_node: {
    name: 'Drain Node',
    description: 'Safely drain a Kubernetes node of workloads before maintenance or replacement.',
    alternatives: [],
    rationale: 'Node requires maintenance or is unhealthy. Draining will safely move workloads to other nodes.',
  },
  toggle_feature_flag: {
    name: 'Toggle Feature Flag',
    description: 'Disable a problematic feature flag to mitigate issues caused by the feature.',
    alternatives: ['rollback_deployment'],
    rationale: 'A specific feature is causing problems. Disabling it will immediately mitigate the issue.',
  },
  restart_container: {
    name: 'Restart Container',
    description: 'Restart a specific container to resolve container-level issues.',
    alternatives: ['restart_service'],
    rationale: 'Container is unresponsive or consuming excessive resources. Restarting will restore normal operation.',
  },
  block_ip: {
    name: 'Block IP Address',
    description: 'Block malicious or problematic IP addresses to prevent attacks or abuse.',
    alternatives: [],
    rationale: 'Specific IP addresses are causing security issues or abuse. Blocking will prevent further impact.',
  },
}

// Generate alternative recommendations based on pattern analysis
function generateAlternativeRecommendations(recommendation, ragContext) {
  const alternatives = []
  const primaryAction = recommendation?.proposed_action
  
  if (!primaryAction || !ACTION_INFO[primaryAction]) {
    return alternatives
  }

  const actionInfo = ACTION_INFO[primaryAction]
  
  // Add primary recommendation
  alternatives.push({
    action: primaryAction,
    name: actionInfo.name,
    description: actionInfo.description,
    rationale: actionInfo.rationale,
    confidence: recommendation.confidence || 0.8,
    riskLevel: recommendation.risk_level || 'MED',
    isPrimary: true,
  })

  // Add alternative actions based on context
  if (actionInfo.alternatives && actionInfo.alternatives.length > 0) {
    actionInfo.alternatives.forEach((altAction, index) => {
      if (ACTION_INFO[altAction]) {
        const altInfo = ACTION_INFO[altAction]
        // Lower confidence for alternatives
        const altConfidence = Math.max(0.3, (recommendation.confidence || 0.8) - 0.2 - (index * 0.1))
        alternatives.push({
          action: altAction,
          name: altInfo.name,
          description: altInfo.description,
          rationale: altInfo.rationale,
          confidence: altConfidence,
          riskLevel: recommendation.risk_level || 'MED',
          isPrimary: false,
        })
      }
    })
  }

  // Analyze pattern context to suggest additional alternatives
  if (ragContext) {
    const contextLower = ragContext.toLowerCase()
    
    // If pattern shows recurring issues, suggest more aggressive actions
    if (contextLower.includes('recurring') || contextLower.includes('systemic')) {
      if (primaryAction === 'restart_service' && !alternatives.find(a => a.action === 'scale_instances')) {
        alternatives.push({
          action: 'scale_instances',
          name: ACTION_INFO.scale_instances.name,
          description: ACTION_INFO.scale_instances.description + ' (Recommended for recurring issues)',
          rationale: 'Pattern analysis indicates recurring issues. Scaling out may provide more permanent relief than restarting.',
          confidence: 0.6,
          riskLevel: 'MED',
          isPrimary: false,
        })
      }
    }

    // If high CPU with memory pressure, suggest both restart and scale
    if (contextLower.includes('cpu') && contextLower.includes('memory')) {
      if (primaryAction === 'restart_service' && !alternatives.find(a => a.action === 'scale_instances')) {
        alternatives.push({
          action: 'scale_instances',
          name: ACTION_INFO.scale_instances.name,
          description: ACTION_INFO.scale_instances.description + ' (Alternative for resource pressure)',
          rationale: 'Both CPU and memory are under pressure. Scaling may be more effective than restarting.',
          confidence: 0.65,
          riskLevel: 'MED',
          isPrimary: false,
        })
      }
    }
  }

  return alternatives
}

export default function AIRecommendationApproval({ incident, ragContext }) {
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [error, setError] = useState(null)
  const [selectedAction, setSelectedAction] = useState(null)

  // Try multiple ways to get recommendation - handle both direct field and meta field
  const recommendation = incident.recommendation || incident.meta?.recommendation || null
  
  // Normalize recommendation structure if it's a plain object
  const normalizedRecommendation = recommendation && typeof recommendation === 'object' && !Array.isArray(recommendation)
    ? {
        root_cause: recommendation.root_cause || '',
        proposed_action: recommendation.proposed_action || '',
        risk_level: recommendation.risk_level || 'MED',
        confidence: typeof recommendation.confidence === 'number' ? recommendation.confidence : 0.8,
      }
    : null

  const manualRequired = Boolean(incident.meta?._manual_review_required)
  const canApprove = incident.state === 'AWAITING_APPROVAL' && Boolean(normalizedRecommendation?.proposed_action)
  const awaitingApproval = incident.state === 'AWAITING_APPROVAL'
  
  // Always show if there's pattern analysis, recommendation, manual review required, or awaiting approval
  const shouldShow = ragContext || normalizedRecommendation || manualRequired || awaitingApproval
  
  if (!shouldShow) return null

  // Generate alternative recommendations
  const allRecommendations = normalizedRecommendation 
    ? generateAlternativeRecommendations(normalizedRecommendation, ragContext)
    : []

  const primaryRecommendation = allRecommendations.find(r => r.isPrimary) || allRecommendations[0]
  const alternativeRecommendations = allRecommendations.filter(r => !r.isPrimary)

  // Use selected action or default to primary
  const actionToApprove = selectedAction || primaryRecommendation?.action || normalizedRecommendation?.proposed_action

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


  const risk = (primaryRecommendation?.riskLevel || normalizedRecommendation?.risk_level || 'MED').toUpperCase()
  const theme = RISK_THEME[risk] || RISK_THEME.MED

  return (
    <div className="space-y-6" style={{ width: '100%', maxWidth: '100%' }}>
      {/* Pattern Analysis Summary */}
      {ragContext && (
        <div 
          className="glass rounded-xl p-5" 
          style={{ 
            borderLeft: '4px solid #818cf8', 
            background: document.body.classList.contains('light-mode')
              ? 'linear-gradient(90deg, rgba(99,102,241,0.08), rgba(168,85,247,0.05))'
              : 'rgba(129,140,248,0.03)',
            border: document.body.classList.contains('light-mode')
              ? '1px solid rgba(99,102,241,0.15)'
              : 'none'
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Info size={14} style={{ color: '#818cf8' }} />
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Pattern Analysis Summary (Human-like SRE Insights)
            </h3>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {(() => {
              // Extract pattern analysis section if it exists
              if (ragContext.includes('=== Pattern Analysis') || ragContext.includes('Pattern Analysis')) {
                // Try to extract just the pattern analysis part (before "Recent Similar Incidents" or "Relevant Runbooks")
                const patternMatch = ragContext.match(/=== Pattern Analysis[^=]*===\s*([\s\S]*?)(?=\n\n(?:Recent Similar Incidents|Relevant Runbooks)|$)/i)
                if (patternMatch && patternMatch[1]) {
                  return (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                      {patternMatch[1].trim()}
                    </div>
                  )
                }
                // Fallback: show everything up to "Recent Similar Incidents" or "Relevant Runbooks"
                const beforeRecent = ragContext.split('Recent Similar Incidents')[0] || ragContext.split('Relevant Runbooks')[0]
                if (beforeRecent && beforeRecent !== ragContext) {
                  return (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                      {beforeRecent.trim()}
                    </div>
                  )
                }
              }
              // If it contains pattern analysis keywords, show the full context
              if (ragContext.includes('Historical Context') || ragContext.includes('Alert Type Patterns') || ragContext.includes('Temporal Patterns')) {
                return (
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                    {ragContext}
                  </div>
                )
              }
              // Default fallback
              return <p>Historical pattern analysis has been performed to inform recommendations.</p>
            })()}
          </div>
        </div>
      )}

      {/* Recommendations Section */}
      <div className="glass rounded-xl p-5" style={{ borderLeft: `4px solid ${theme.border}`, background: theme.bg }}>
        <div className="flex items-start justify-between mb-5">
          <div>
            <h3 className="flex items-center gap-2" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <Sparkles size={14} style={{ color: '#818cf8' }} />
              AI Recommendation & Approval
            </h3>
            {primaryRecommendation && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                CONFIDENCE: {(primaryRecommendation.confidence * 100).toFixed(1)}%
              </p>
            )}
          </div>
          <span
            className="px-2.5 py-1 rounded-md"
            style={{ fontSize: 11, fontWeight: 700, color: theme.border, background: 'var(--bg-input)', border: `1px solid ${theme.border}30` }}
          >
            {risk} RISK
          </span>
        </div>

        {allRecommendations.length === 0 ? (
          <div className="space-y-4">
            <div className="p-4 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <div className="flex items-start gap-3">
                <AlertCircle size={16} style={{ color: '#f59e0b', marginTop: 2, flexShrink: 0 }} />
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
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#818cf8', marginBottom: 2 }}>Pattern Analysis Available:</p>
                      <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        Historical patterns and context have been analyzed. Review the Pattern Analysis Summary above for insights. Based on the patterns detected, you may want to consider manual actions such as investigating the recurring issues or reviewing scheduled jobs.
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
            {primaryRecommendation && (
              <div 
                className="p-4 rounded-lg transition-all"
                style={{ 
                  background: selectedAction === primaryRecommendation.action ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                  border: `2px solid ${selectedAction === primaryRecommendation.action ? '#818cf8' : 'var(--border)'}`,
                  cursor: 'pointer'
                }}
                onClick={() => setSelectedAction(primaryRecommendation.action)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={16} style={{ color: '#10b981' }} />
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)' }}>
                      Primary Recommendation
                    </span>
                    <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: '#10b981', background: 'rgba(16,185,129,0.1)' }}>
                      {(primaryRecommendation.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  {selectedAction === primaryRecommendation.action && (
                    <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: '#818cf8', color: 'white' }}>
                      <CheckCircle2 size={12} />
                    </div>
                  )}
                </div>
                <div className="mb-2">
                  <div className="p-3 rounded-lg mb-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: '#818cf8', background: 'var(--terminal-bg)', border: '1px solid rgba(99,102,241,0.1)' }}>
                    <span style={{ color: 'rgba(99,102,241,0.4)', marginRight: 4 }}>$</span>
                    {primaryRecommendation.action}
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 8, fontWeight: 500 }}>
                    {primaryRecommendation.name}
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
                    {primaryRecommendation.description}
                  </p>
                  <div className="p-3 rounded" style={{ background: 'rgba(129,140,248,0.05)', border: '1px solid rgba(129,140,248,0.1)' }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: '#818cf8', marginBottom: 4 }}>Rationale:</p>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {primaryRecommendation.rationale}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Alternative Recommendations */}
            {alternativeRecommendations.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle size={14} style={{ color: 'var(--text-muted)' }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Alternative Options
                  </span>
                </div>
                <div className="space-y-3">
                  {alternativeRecommendations.map((alt, index) => (
                    <div
                      key={alt.action}
                      className="p-4 rounded-lg transition-all"
                      style={{ 
                        background: selectedAction === alt.action ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                        border: `1px solid ${selectedAction === alt.action ? '#818cf8' : 'var(--border)'}`,
                        cursor: 'pointer'
                      }}
                      onClick={() => setSelectedAction(alt.action)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-heading)' }}>
                            Option {index + 1}
                          </span>
                          <span className="px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: '#f59e0b', background: 'rgba(245,158,11,0.1)' }}>
                            {(alt.confidence * 100).toFixed(0)}% confidence
                          </span>
                        </div>
                        {selectedAction === alt.action && (
                          <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: '#818cf8', color: 'white' }}>
                            <CheckCircle2 size={12} />
                          </div>
                        )}
                      </div>
                      <div className="mb-2">
                        <div className="p-2 rounded mb-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#818cf8', background: 'var(--terminal-bg)', border: '1px solid rgba(99,102,241,0.1)' }}>
                          <span style={{ color: 'rgba(99,102,241,0.4)', marginRight: 4 }}>$</span>
                          {alt.action}
                        </div>
                        <p style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 6, fontWeight: 500 }}>
                          {alt.name}
                        </p>
                        <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 6 }}>
                          {alt.description}
                        </p>
                        <div className="p-2 rounded" style={{ background: 'rgba(129,140,248,0.03)', border: '1px solid rgba(129,140,248,0.08)' }}>
                          <p style={{ fontSize: 10, fontWeight: 600, color: '#818cf8', marginBottom: 2 }}>Why this option:</p>
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
              <p className="mb-4 px-3 py-2 rounded-md" style={{ fontSize: 12, color: '#fb7185', background: 'rgba(244,63,94,0.1)' }}>{error}</p>
            )}

            <div className="flex gap-3 flex-wrap">
              <button
                onClick={() => setModalOpen(true)}
                disabled={loading || !actionToApprove}
                className="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 12px rgba(99,102,241,0.2)' }}
              >
                {loading ? (
                  <>
                    <Loader size={14} className="animate-spin" /> Processing...
                  </>
                ) : (
                  <>
                    <ShieldCheck size={14} /> Approve & Execute
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        <ConfirmationModal
          open={modalOpen}
          title="Confirm Execution"
          message={
            <div className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <p>You are about to execute <strong style={{ fontFamily: 'var(--font-mono)', color: '#818cf8' }}>{actionToApprove}</strong> on this incident.</p>
              {primaryRecommendation && selectedAction === primaryRecommendation.action && (
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  This is the primary recommendation with {(primaryRecommendation.confidence * 100).toFixed(0)}% confidence.
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
