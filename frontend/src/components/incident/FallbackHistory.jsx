import { useState } from 'react'
import { useTheme } from '../../context/ThemeContext'
import {
  RotateCcw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react'
import { formatTimestamp } from '../../utils/formatters'

const STATUS_CONFIG = {
  verification_failed: {
    label: 'Verification Failed',
    color: '#f87171',
    bg: 'rgba(248,113,113,0.1)',
    border: 'rgba(248,113,113,0.25)',
    Icon: XCircle,
  },
  policy_rejected: {
    label: 'Policy Rejected',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.1)',
    border: 'rgba(245,158,11,0.25)',
    Icon: ShieldAlert,
  },
  executing: {
    label: 'Executing',
    color: '#3b82f6',
    bg: 'rgba(59,130,246,0.1)',
    border: 'rgba(59,130,246,0.25)',
    Icon: RotateCcw,
  },
}

export default function FallbackHistory({ incident }) {
  const { isDark } = useTheme()
  const [expanded, setExpanded] = useState(false)

  const meta = incident?.meta || {}
  const fallbackHistory = meta._fallback_history || []
  const isFallback = meta._is_fallback || false
  const fallbackFrom = meta._fallback_from || ''
  const originalAction = meta._original_proposed_action || ''
  const currentAction = meta.recommendation?.proposed_action || ''

  if (fallbackHistory.length === 0 && !isFallback) {
    return null
  }

  return (
    <div
      className="glass rounded-xl overflow-hidden transition-all"
      style={{
        borderLeft: '3px solid rgba(251,191,36,0.5)',
        background: isDark ? 'rgba(251,191,36,0.03)' : '#FFFBEB',
        border: isDark ? undefined : '1px solid #FDE68A',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left transition-colors"
        style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
        aria-label="Toggle fallback history"
      >
        <div className="flex items-center gap-2">
          <RotateCcw
            size={14}
            style={{ color: '#f59e0b' }}
          />
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}
          >
            Fallback History
          </span>
          <span
            className="inline-flex items-center justify-center rounded-full"
            style={{
              fontSize: 10,
              fontWeight: 700,
              width: 18,
              height: 18,
              background: 'rgba(251,191,36,0.15)',
              color: '#f59e0b',
              border: '1px solid rgba(251,191,36,0.3)',
            }}
          >
            {fallbackHistory.length}
          </span>
          {isFallback && (
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: '#f59e0b',
                background: 'rgba(251,191,36,0.12)',
                border: '1px solid rgba(251,191,36,0.25)',
              }}
            >
              <AlertTriangle size={10} />
              Using fallback action
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} />
        ) : (
          <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Flow summary */}
          {originalAction && (
            <div
              className="flex items-center gap-2 flex-wrap p-2 rounded-lg"
              style={{
                fontSize: 12,
                background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)',
              }}
            >
              <span
                className="px-2 py-0.5 rounded"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                  color: '#f87171',
                  background: 'rgba(248,113,113,0.1)',
                  textDecoration: 'line-through',
                }}
              >
                {originalAction}
              </span>
              <ArrowRight size={12} style={{ color: 'var(--text-muted)' }} />
              <span
                className="px-2 py-0.5 rounded"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  fontWeight: 600,
                  color: '#10b981',
                  background: 'rgba(16,185,129,0.1)',
                }}
              >
                {currentAction}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                (current)
              </span>
            </div>
          )}

          {/* History entries */}
          {fallbackHistory.map((entry, idx) => {
            const config = STATUS_CONFIG[entry.status] || STATUS_CONFIG.verification_failed
            const StatusIcon = config.Icon
            return (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 rounded-lg"
                style={{
                  background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
                  border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)',
                }}
              >
                <div
                  className="flex items-center justify-center rounded-full flex-shrink-0 mt-0.5"
                  style={{
                    width: 24,
                    height: 24,
                    background: config.bg,
                    border: `1px solid ${config.border}`,
                  }}
                >
                  <StatusIcon size={12} style={{ color: config.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                        fontWeight: 600,
                        color: 'var(--text-heading)',
                      }}
                    >
                      {entry.action}
                    </span>
                    <span
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded"
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: config.color,
                        background: config.bg,
                        border: `1px solid ${config.border}`,
                      }}
                    >
                      {config.label}
                    </span>
                  </div>
                  {entry.reason && (
                    <p
                      style={{
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                        marginTop: 4,
                      }}
                    >
                      {entry.reason}
                    </p>
                  )}
                  {entry.attempted_at && (
                    <span
                      style={{
                        fontSize: 10,
                        color: 'var(--text-muted)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {formatTimestamp(entry.attempted_at)}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
