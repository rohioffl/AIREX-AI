import { useState } from 'react'
import { CheckCircle, XCircle, Clock, ThumbsUp, ThumbsDown, Star, Send, Loader, AlertTriangle } from 'lucide-react'
import { submitFeedback } from '../../services/api'
import { extractErrorMessage } from '../../utils/errorHandler'

const RESOLUTION_TYPE_CONFIG = {
  auto: { label: 'Autonomous Resolution', color: 'var(--color-accent-green)', icon: CheckCircle, desc: 'Fully automated: auto-approved, executed, and verified without human intervention.' },
  operator: { label: 'Operator-Approved', color: 'var(--neon-indigo)', icon: CheckCircle, desc: 'Operator approved the recommended action which was then executed automatically.' },
  senior: { label: 'Senior-Approved', color: 'var(--neon-purple)', icon: CheckCircle, desc: 'Senior/admin approved this high-impact action before execution.' },
  rejected: { label: 'Rejected by Operator', color: 'var(--color-accent-red)', icon: XCircle, desc: 'Operator rejected the automated recommendation.' },
  failed: { label: 'Resolution Failed', color: 'var(--color-accent-red)', icon: AlertTriangle, desc: 'Automated resolution did not succeed. Manual intervention may be needed.' },
  manual: { label: 'Manual Resolution', color: 'var(--color-accent-amber)', icon: CheckCircle, desc: 'Resolved through manual intervention outside the automation pipeline.' },
}

const SCORE_OPTIONS = [
  { value: -1, label: 'Harmful', icon: ThumbsDown, color: 'var(--color-accent-red)', desc: 'Made things worse' },
  { value: 0, label: 'Ineffective', icon: XCircle, color: 'var(--color-accent-amber)', desc: 'No impact' },
  { value: 1, label: 'Poor', icon: Star, color: 'var(--brand-orange)', desc: 'Barely helpful' },
  { value: 2, label: 'Fair', icon: Star, color: '#eab308', desc: 'Some value' },
  { value: 3, label: 'Good', icon: Star, color: '#84cc16', desc: 'Helpful' },
  { value: 4, label: 'Great', icon: Star, color: '#22c55e', desc: 'Very helpful' },
  { value: 5, label: 'Excellent', icon: ThumbsUp, color: 'var(--color-accent-green)', desc: 'Perfect resolution' },
]

function formatDuration(seconds) {
  if (seconds == null) return null
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

export default function ResolutionOutcome({ incident }) {
  const [feedbackScore, setFeedbackScore] = useState(incident.feedback_score)
  const [feedbackNote, setFeedbackNote] = useState(incident.feedback_note || '')
  const [selectedScore, setSelectedScore] = useState(incident.feedback_score)
  const [noteInput, setNoteInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [submitted, setSubmitted] = useState(incident.feedback_score != null)

  const resolutionType = incident.resolution_type
  const resolutionSummary = incident.resolution_summary
  const durationSeconds = incident.resolution_duration_seconds

  // Only show for terminal states with resolution data
  const terminalStates = new Set(['RESOLVED', 'REJECTED', 'FAILED_EXECUTION', 'FAILED_VERIFICATION'])
  if (!terminalStates.has(incident.state)) return null

  const config = RESOLUTION_TYPE_CONFIG[resolutionType] || RESOLUTION_TYPE_CONFIG.manual
  const Icon = config.icon
  const duration = formatDuration(durationSeconds)

  async function handleSubmitFeedback() {
    if (selectedScore == null) return
    setSubmitting(true)
    setError(null)
    try {
      await submitFeedback(incident.id, selectedScore, noteInput || null)
      setFeedbackScore(selectedScore)
      setFeedbackNote(noteInput)
      setSubmitted(true)
    } catch (err) {
      setError(extractErrorMessage(err) || err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="glass rounded-xl p-5 space-y-4" style={{ borderLeft: `4px solid ${config.color}`, background: `${config.color}06` }}>
      {/* Resolution Header */}
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-full" style={{ background: `${config.color}15`, border: `1px solid ${config.color}30`, color: config.color }}>
          <Icon size={18} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 style={{ fontSize: 14, fontWeight: 700, color: config.color }}>{config.label}</h3>
            {duration && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded" style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                <Clock size={10} />
                {duration}
              </span>
            )}
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{config.desc}</p>
        </div>
      </div>

      {/* Resolution Summary */}
      {resolutionSummary && (
        <div className="rounded-lg p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Resolution Summary</span>
          <p style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4, lineHeight: 1.6, fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap' }}>
            {resolutionSummary}
          </p>
        </div>
      )}

      {/* Feedback Section */}
      <div className="rounded-lg p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {submitted ? 'Operator Feedback' : 'Rate This Resolution'}
        </span>

        {submitted ? (
          <div className="mt-3 flex items-center gap-3">
            {SCORE_OPTIONS.filter(o => o.value === feedbackScore).map(o => (
              <span key={o.value} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg" style={{ fontSize: 12, fontWeight: 700, color: o.color, background: `${o.color}15`, border: `1px solid ${o.color}30` }}>
                <o.icon size={14} />
                {o.label} ({o.value})
              </span>
            ))}
            {feedbackNote && (
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                "{feedbackNote}"
              </span>
            )}
          </div>
        ) : (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap gap-2">
              {SCORE_OPTIONS.map(o => (
                <button
                  key={o.value}
                  onClick={() => setSelectedScore(o.value)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition-all"
                  style={{
                    fontSize: 11,
                    fontWeight: selectedScore === o.value ? 700 : 500,
                    color: selectedScore === o.value ? o.color : 'var(--text-secondary)',
                    background: selectedScore === o.value ? `${o.color}15` : 'transparent',
                    border: `1px solid ${selectedScore === o.value ? `${o.color}50` : 'var(--border)'}`,
                  }}
                  title={o.desc}
                >
                  <o.icon size={12} />
                  {o.label}
                </button>
              ))}
            </div>
            <div>
              <input
                type="text"
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value.slice(0, 200))}
                placeholder="Optional: explain your rating..."
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-card)',
                  color: 'var(--text-primary)',
                  fontSize: 12,
                }}
                disabled={submitting}
              />
            </div>
            {error && (
              <p style={{ fontSize: 11, color: 'var(--color-accent-red)' }}>{error}</p>
            )}
            <button
              onClick={handleSubmitFeedback}
              disabled={selectedScore == null || submitting}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50"
              style={{ background: 'var(--gradient-primary)' }}
            >
              {submitting ? <><Loader size={12} className="animate-spin" /> Submitting...</> : <><Send size={12} /> Submit Feedback</>}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
