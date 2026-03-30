import { useState, useEffect } from 'react'
import { Brain, Copy, ChevronDown, BookOpen, History, TrendingUp, AlertCircle } from 'lucide-react'

// Animated Thinking Indicator
function ThinkingIndicator() {
  const [textIndex, setTextIndex] = useState(0);
  const texts = [
    "Analyzing evidence...",
    "Correlating patterns...",
    "Generating recommendations..."
  ];

  useEffect(() => {
    const timer = setInterval(() => {
      setTextIndex((prev) => (prev + 1) % texts.length);
    }, 2500);
    return () => clearInterval(timer);
  }, [texts.length]);

  return (
    <div className="flex items-center gap-2 mt-1">
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
        {texts[textIndex]}
      </div>
      <div className="flex items-center gap-1" style={{ color: 'var(--neon-indigo)' }}>
        <span className="thinking-dot"></span>
        <span className="thinking-dot"></span>
        <span className="thinking-dot"></span>
      </div>
    </div>
  );
}

// Score badge with color based on similarity score
function ScoreBadge({ score }) {
  if (score == null) return null
  const pct = Math.round(score * 100)
  const color = pct >= 80 ? 'var(--color-accent-green)' : pct >= 60 ? 'var(--color-accent-amber)' : 'var(--text-muted)'
  return (
    <span
      className="inline-flex items-center rounded-full px-1.5 py-0.5"
      style={{
        fontSize: 9,
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        color,
        background: `${color}15`,
        border: `1px solid ${color}30`,
      }}
    >
      {pct}%
    </span>
  )
}

function SimilarIncidentCard({ incident }) {
  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: 'var(--bg-input)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <History size={12} style={{ color: 'var(--neon-cyan)', flexShrink: 0 }} />
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {incident.incident_id ? incident.incident_id.substring(0, 8) : 'Past Incident'}
          </span>
        </div>
        <ScoreBadge score={incident.score} />
      </div>
      {incident.snippet && (
        <p
          style={{
            fontSize: 11,
            color: 'var(--text-muted)',
            marginTop: 4,
            lineHeight: 1.4,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {incident.snippet}
        </p>
      )}
    </div>
  )
}

function PatternAnalysisCard({ pattern }) {
  if (!pattern) return null
  const { historical_context, recurrence_count, avg_resolution_time_minutes, most_effective_action } = pattern
  const hasData = historical_context || recurrence_count || avg_resolution_time_minutes || most_effective_action
  if (!hasData) return null

  return (
    <div
      className="rounded-lg p-3"
      style={{
        background: 'rgba(129,140,248,0.04)',
        border: '1px solid rgba(129,140,248,0.15)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <TrendingUp size={12} style={{ color: 'var(--neon-indigo)' }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--neon-indigo)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Pattern Analysis
        </span>
      </div>
      <div className="space-y-2">
        {historical_context && (
          <p style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.4 }}>
            {historical_context}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          {recurrence_count != null && recurrence_count > 0 && (
            <div className="flex items-center gap-1.5">
              <AlertCircle size={10} style={{ color: 'var(--text-muted)' }} />
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                Seen <strong style={{ color: 'var(--text-primary)' }}>{recurrence_count}</strong> time{recurrence_count !== 1 ? 's' : ''} before
              </span>
            </div>
          )}
          {avg_resolution_time_minutes != null && avg_resolution_time_minutes > 0 && (
            <div className="flex items-center gap-1.5">
              <History size={10} style={{ color: 'var(--text-muted)' }} />
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                Avg resolution: <strong style={{ color: 'var(--text-primary)' }}>{avg_resolution_time_minutes}m</strong>
              </span>
            </div>
          )}
          {most_effective_action && (
            <div className="flex items-center gap-1.5">
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                Best action: <strong style={{ color: 'var(--color-accent-green)' }}>{most_effective_action}</strong>
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Helper to get a preview of the analysis
function getAnalysisPreview(ragStructured, ragContext) {
  if (ragStructured) {
    const parts = []
    if (ragStructured.runbook_count) parts.push(`${ragStructured.runbook_count} runbook${ragStructured.runbook_count !== 1 ? 's' : ''}`)
    if (ragStructured.incident_count) parts.push(`${ragStructured.incident_count} similar incident${ragStructured.incident_count !== 1 ? 's' : ''}`)
    if (ragStructured.pattern_analysis?.recurrence_count) parts.push(`${ragStructured.pattern_analysis.recurrence_count} past occurrences`)
    return parts.length > 0 ? parts.join(' | ') : 'Analysis available'
  }
  if (!ragContext) return 'No analysis available'
  const lines = ragContext.split('\n').filter(l => l.trim() && !l.startsWith('===') && !l.startsWith('---'))
  const preview = lines.slice(0, 3).join(' ')
  if (preview.length <= 150) return preview
  return preview.substring(0, 147) + '...'
}

export default function AIAnalysisPanel({ incident }) {
  const [expanded, setExpanded] = useState(false)

  const ragStructured = incident?.meta?.rag_structured || null
  const ragContext = incident?.rag_context || null
  const recommendation = incident?.recommendation || null

  const hasStructured = ragStructured && (
    (ragStructured.runbooks && ragStructured.runbooks.length > 0) ||
    (ragStructured.similar_incidents && ragStructured.similar_incidents.length > 0) ||
    ragStructured.pattern_analysis
  )

  const hasContent = hasStructured || ragContext || recommendation?.root_cause

  if (!hasContent) {
    return (
      <div className="glass rounded-xl overflow-hidden" style={{ width: '100%', boxSizing: 'border-box', borderLeft: '4px solid var(--neon-indigo)' }}>
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(129,140,248,0.1)', color: 'var(--neon-indigo)' }}>
              <Brain size={16} style={{ animation: 'var(--animate-glow-pulse)' }} />
            </div>
            <div>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                AI Investigation
              </h3>
              <ThinkingIndicator />
            </div>
          </div>
        </div>
      </div>
    )
  }

  const preview = getAnalysisPreview(ragStructured, ragContext)

  return (
    <div className="glass rounded-xl overflow-hidden" style={{ width: '100%', boxSizing: 'border-box', borderLeft: '4px solid var(--neon-indigo)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-5 py-4 w-full text-left transition-colors"
        style={{
          background: 'transparent',
          borderBottom: expanded ? '1px solid var(--border)' : 'none'
        }}
        onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
        onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(129,140,248,0.1)', color: 'var(--neon-indigo)' }}>
            <Brain size={16} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              AI Investigation
            </h3>
            {!expanded && (
              <p style={{
                fontSize: 11,
                color: 'var(--text-muted)',
                marginTop: 4,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {preview}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {hasStructured && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--neon-indigo)', padding: '2px 6px', borderRadius: 4, background: 'rgba(129,140,248,0.1)' }}>
              STRUCTURED
            </span>
          )}
          <ChevronDown
            size={16}
            style={{
              color: 'var(--text-muted)',
              transform: expanded ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s'
            }}
          />
        </div>
      </button>

      {expanded && (
        <div className="p-5" style={{ borderTop: '1px solid var(--border)' }}>
          {hasStructured ? (
            <div className="space-y-4">
              {/* Root cause from recommendation */}
              {recommendation?.root_cause && (
                <div className="rounded-lg p-3" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Root Cause</span>
                  <p style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4, lineHeight: 1.5 }}>
                    {recommendation.root_cause}
                  </p>
                </div>
              )}

              {/* Pattern Analysis */}
              <PatternAnalysisCard pattern={ragStructured.pattern_analysis} />

              {/* Similar Incidents */}
              {ragStructured.similar_incidents && ragStructured.similar_incidents.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Similar Incidents
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', padding: '2px 6px', borderRadius: 4, background: 'var(--bg-input)' }}>
                      {ragStructured.similar_incidents.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {ragStructured.similar_incidents.map((si, idx) => (
                      <SimilarIncidentCard key={idx} incident={si} />
                    ))}
                  </div>
                </div>
              )}

              {/* Copy raw context button */}
              {ragContext && (
                <div className="flex justify-end">
                  <button
                    onClick={(ev) => {
                      ev.stopPropagation()
                      navigator.clipboard.writeText(ragContext)
                    }}
                    className="flex items-center gap-1 px-2 py-1 rounded transition-colors"
                    style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', background: 'var(--bg-input)' }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Copy size={11} /> Copy Raw Context
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Legacy fallback: render raw text */
            <div>
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Full Analysis</span>
                </div>
                <button
                  onClick={(ev) => {
                    ev.stopPropagation()
                    navigator.clipboard.writeText(ragContext || recommendation?.root_cause || '')
                  }}
                  className="flex items-center gap-1 px-2 py-1 rounded transition-colors"
                  style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', background: 'var(--bg-input)' }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
                  onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                >
                  <Copy size={11} /> Copy
                </button>
              </div>
              <div className="relative rounded" style={{
                maxHeight: '600px',
                overflow: 'auto',
                background: 'var(--bg-input)',
                padding: '12px',
                border: '1px solid var(--border)'
              }}>
                <pre style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--text-primary)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.5,
                  margin: 0,
                  padding: 0
                }}>
                  {ragContext || `Root Cause Analysis:\n\n${recommendation?.root_cause}`}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
