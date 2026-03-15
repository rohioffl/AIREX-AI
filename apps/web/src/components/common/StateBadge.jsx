const STATE_CONFIG = {
  RECEIVED:              { bg: 'rgba(96,165,250,0.1)',  text: '#60a5fa', border: 'rgba(96,165,250,0.2)', bgLight: 'rgba(96,165,250,0.1)', textLight: '#60a5fa', borderLight: 'rgba(96,165,250,0.2)' },
  INVESTIGATING:         { bg: 'rgba(129,140,248,0.1)', text: 'var(--neon-indigo)', border: 'rgba(129,140,248,0.2)', bgLight: 'rgba(129,140,248,0.1)', textLight: 'var(--neon-indigo)', borderLight: 'rgba(129,140,248,0.2)' },
  RECOMMENDATION_READY:  { bg: 'rgba(167,139,250,0.1)', text: '#a78bfa', border: 'rgba(167,139,250,0.2)', bgLight: 'rgba(167,139,250,0.1)', textLight: '#a78bfa', borderLight: 'rgba(167,139,250,0.2)' },
  AWAITING_APPROVAL:     { bg: 'rgba(251,191,36,0.1)',  text: '#fbbf24', border: 'rgba(251,191,36,0.2)', bgLight: '#FEF3C7', textLight: '#92400E', borderLight: 'rgba(251,191,36,0.3)' },
  EXECUTING:             { bg: 'rgba(56,189,248,0.1)',  text: '#38bdf8', border: 'rgba(56,189,248,0.2)', bgLight: 'rgba(56,189,248,0.1)', textLight: '#38bdf8', borderLight: 'rgba(56,189,248,0.2)' },
  VERIFYING:             { bg: 'rgba(34,211,238,0.1)',  text: 'var(--neon-cyan)', border: 'rgba(34,211,238,0.2)', bgLight: 'rgba(34,211,238,0.1)', textLight: 'var(--neon-cyan)', borderLight: 'rgba(34,211,238,0.2)' },
  RESOLVED:              { bg: 'rgba(52,211,153,0.1)',  text: 'var(--neon-green)', border: 'rgba(52,211,153,0.2)', bgLight: 'rgba(52,211,153,0.1)', textLight: 'var(--neon-green)', borderLight: 'rgba(52,211,153,0.2)' },
  FAILED_ANALYSIS:       { bg: 'rgba(251,113,133,0.1)', text: 'var(--color-accent-red)', border: 'rgba(251,113,133,0.2)', bgLight: 'rgba(251,113,133,0.1)', textLight: 'var(--color-accent-red)', borderLight: 'rgba(251,113,133,0.2)' },
  FAILED_EXECUTION:      { bg: 'rgba(251,113,133,0.1)', text: 'var(--color-accent-red)', border: 'rgba(251,113,133,0.2)', bgLight: 'rgba(251,113,133,0.1)', textLight: 'var(--color-accent-red)', borderLight: 'rgba(251,113,133,0.2)' },
  FAILED_VERIFICATION:   { bg: 'rgba(251,113,133,0.1)', text: 'var(--color-accent-red)', border: 'rgba(251,113,133,0.2)', bgLight: 'rgba(251,113,133,0.1)', textLight: 'var(--color-accent-red)', borderLight: 'rgba(251,113,133,0.2)' },
}

const FALLBACK = { bg: 'rgba(148,163,184,0.1)', text: '#94a3b8', border: 'rgba(148,163,184,0.2)', bgLight: 'rgba(148,163,184,0.1)', textLight: '#94a3b8', borderLight: 'rgba(148,163,184,0.2)' }

export default function StateBadge({ state }) {
  const c = STATE_CONFIG[state] || FALLBACK
  const isLightMode = document.body.classList.contains('light-mode')
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1"
      style={{ 
        background: isLightMode && state === 'AWAITING_APPROVAL' ? c.bgLight : c.bg, 
        color: isLightMode && state === 'AWAITING_APPROVAL' ? c.textLight : c.text, 
        border: `1px solid ${isLightMode && state === 'AWAITING_APPROVAL' ? c.borderLight : c.border}`, 
        fontSize: 11, 
        fontWeight: 600, 
        letterSpacing: '0.03em' 
      }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: isLightMode && state === 'AWAITING_APPROVAL' ? c.textLight : c.text }} />
      {state}
    </span>
  )
}
