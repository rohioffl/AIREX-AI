const SEVERITY_CONFIG = {
  CRITICAL: { bg: 'rgba(244,63,94,0.12)',  text: '#fb7185', icon: '!!' },
  HIGH:     { bg: 'rgba(251,146,60,0.12)', text: '#fb923c', icon: '!' },
  MEDIUM:   { bg: 'rgba(250,204,21,0.1)',  text: '#facc15', icon: '~' },
  LOW:      { bg: 'rgba(96,165,250,0.1)',  text: '#60a5fa', icon: '-' },
}

const FALLBACK = { bg: 'rgba(148,163,184,0.1)', text: '#94a3b8', icon: '?' }

export default function SeverityBadge({ severity }) {
  const c = SEVERITY_CONFIG[severity] || FALLBACK
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-2 py-0.5"
      style={{ background: c.bg, color: c.text, fontSize: 11, fontWeight: 700, letterSpacing: '0.05em' }}
    >
      <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.6 }}>{c.icon}</span>
      {severity}
    </span>
  )
}
