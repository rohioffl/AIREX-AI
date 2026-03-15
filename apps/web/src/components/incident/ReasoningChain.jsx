import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

export default function ReasoningChain({ reasoningChain, verificationCriteria }) {
  const [expanded, setExpanded] = useState(false)

  if ((!reasoningChain || reasoningChain.length === 0) && (!verificationCriteria || verificationCriteria.length === 0)) {
    return null
  }

  return (
    <div className="mt-4 rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-4 py-3 w-full text-left transition-colors"
        style={{ background: 'var(--bg-input)' }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          AI Reasoning Chain {reasoningChain?.length ? `(${reasoningChain.length} steps)` : ''}
        </span>
        <ChevronDown
          size={14}
          style={{
            color: 'var(--text-muted)',
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s',
          }}
        />
      </button>

      {expanded && (
        <div className="p-4 space-y-4" style={{ borderTop: '1px solid var(--border)' }}>
          {/* Reasoning steps */}
          {reasoningChain && reasoningChain.length > 0 && (
            <div className="space-y-2">
              {reasoningChain.map((step, idx) => (
                <div
                  key={idx}
                  className="flex gap-3 py-2 px-3 rounded-lg"
                  style={{ background: 'rgba(129,140,248,0.03)', borderLeft: '2px solid var(--neon-indigo)' }}
                >
                  <div
                    className="flex items-center justify-center rounded-full flex-shrink-0"
                    style={{
                      width: 22,
                      height: 22,
                      fontSize: 10,
                      fontWeight: 700,
                      color: 'var(--neon-indigo)',
                      background: 'rgba(129,140,248,0.1)',
                      border: '1px solid rgba(129,140,248,0.2)',
                    }}
                  >
                    {step.step || idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                      {step.description}
                    </p>
                    {step.evidence_used && (
                      <p style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                        Evidence: {step.evidence_used}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Verification criteria */}
          {verificationCriteria && verificationCriteria.length > 0 && (
            <div>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Verification Criteria
              </span>
              <ul className="mt-2 space-y-1">
                {verificationCriteria.map((criterion, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 py-1 px-3 rounded"
                    style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(16,185,129,0.03)' }}
                  >
                    <span style={{ color: 'var(--color-accent-green)', flexShrink: 0, marginTop: 1 }}>{'\u2713'}</span>
                    {criterion}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
