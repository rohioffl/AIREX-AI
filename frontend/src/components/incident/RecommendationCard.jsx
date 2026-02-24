import { Sparkles, BookOpen } from 'lucide-react'

const RISK_THEME = {
  LOW:  { border: '#10b981', bg: 'rgba(16,185,129,0.04)' },
  MED:  { border: '#f59e0b', bg: 'rgba(245,158,11,0.04)' },
  HIGH: { border: '#f43f5e', bg: 'rgba(244,63,94,0.04)' },
}

const SHOW_STATES = new Set([
  'RECOMMENDATION_READY', 'AWAITING_APPROVAL', 'EXECUTING', 'VERIFYING',
  'RESOLVED', 'FAILED_ANALYSIS', 'FAILED_EXECUTION', 'FAILED_VERIFICATION',
])

export default function RecommendationCard({ recommendation, state, ragContext }) {
  if (!recommendation) {
    if (!SHOW_STATES.has(state)) {
      return (
        <div className="glass rounded-xl p-6 text-center">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-full shimmer mb-3" style={{ background: 'var(--bg-input)', color: 'var(--text-muted)' }}>
            <Sparkles size={18} />
          </div>
          <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>Analysis in Progress...</p>
        </div>
      )
    }
    return (
      <div className="glass rounded-xl p-5">
        <div className="h-4 w-1/3 rounded shimmer mb-3" style={{ background: 'var(--bg-input)' }} />
        <div className="h-16 w-full rounded shimmer" style={{ background: 'var(--bg-input)' }} />
      </div>
    )
  }

  const risk = recommendation.risk_level || 'LOW'
  const theme = RISK_THEME[risk] || RISK_THEME.LOW

  return (
    <div className="glass rounded-xl p-5" style={{ borderLeft: `4px solid ${theme.border}`, background: theme.bg }}>
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="flex items-center gap-2" style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            <Sparkles size={14} style={{ color: '#818cf8' }} />
            AI Recommendation
          </h3>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            CONFIDENCE: {(recommendation.confidence * 100).toFixed(1)}%
          </p>
        </div>
        <span
          className="px-2.5 py-1 rounded-md"
          style={{ fontSize: 11, fontWeight: 700, color: theme.border, background: 'var(--bg-input)', border: `1px solid ${theme.border}30` }}
        >
          {risk} RISK
        </span>
      </div>

      <div className="space-y-4">
        <div>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 6 }}>Root Cause</span>
          <p className="p-3 rounded-lg" style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            {recommendation.root_cause}
          </p>
        </div>
        <div>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 6 }}>Proposed Action</span>
          <div className="p-3 rounded-lg" style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: '#818cf8', background: 'var(--terminal-bg)', border: '1px solid rgba(99,102,241,0.1)' }}>
            <span style={{ color: 'rgba(99,102,241,0.4)', marginRight: 4 }}>$</span>
            {recommendation.proposed_action}
          </div>
        </div>

        {ragContext && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <BookOpen size={14} style={{ color: 'var(--text-muted)' }} />
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>AI Context & Reasoning</span>
            </div>
            <div className="p-3 rounded-lg" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)', background: 'var(--bg-input)', border: '1px solid var(--border)', maxHeight: '200px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
              {ragContext}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
