const STATE_CONFIG = {
  RECEIVED:              { bg: 'rgba(96,165,250,0.1)',  text: '#60a5fa', border: 'rgba(96,165,250,0.2)' },
  INVESTIGATING:         { bg: 'rgba(129,140,248,0.1)', text: '#818cf8', border: 'rgba(129,140,248,0.2)' },
  RECOMMENDATION_READY:  { bg: 'rgba(167,139,250,0.1)', text: '#a78bfa', border: 'rgba(167,139,250,0.2)' },
  AWAITING_APPROVAL:     { bg: 'rgba(251,191,36,0.1)',  text: '#fbbf24', border: 'rgba(251,191,36,0.2)' },
  EXECUTING:             { bg: 'rgba(56,189,248,0.1)',  text: '#38bdf8', border: 'rgba(56,189,248,0.2)' },
  VERIFYING:             { bg: 'rgba(34,211,238,0.1)',  text: '#22d3ee', border: 'rgba(34,211,238,0.2)' },
  RESOLVED:              { bg: 'rgba(52,211,153,0.1)',  text: '#34d399', border: 'rgba(52,211,153,0.2)' },
  FAILED_ANALYSIS:       { bg: 'rgba(251,113,133,0.1)', text: '#fb7185', border: 'rgba(251,113,133,0.2)' },
  FAILED_EXECUTION:      { bg: 'rgba(251,113,133,0.1)', text: '#fb7185', border: 'rgba(251,113,133,0.2)' },
  FAILED_VERIFICATION:   { bg: 'rgba(251,113,133,0.1)', text: '#fb7185', border: 'rgba(251,113,133,0.2)' },
}

const FALLBACK = { bg: 'rgba(148,163,184,0.1)', text: '#94a3b8', border: 'rgba(148,163,184,0.2)' }

export default function StateBadge({ state }) {
  const c = STATE_CONFIG[state] || FALLBACK
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}`, fontSize: 11, fontWeight: 600, letterSpacing: '0.03em' }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: c.text }} />
      {state}
    </span>
  )
}
