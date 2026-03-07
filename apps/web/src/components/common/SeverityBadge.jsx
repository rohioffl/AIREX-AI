const SEVERITY_CONFIG = {
  CRITICAL: { bg: 'rgba(244,63,94,0.12)',  text: '#fb7185', bgLight: '#FEE2E2', textLight: '#991B1B' },
  HIGH:     { bg: 'rgba(251,146,60,0.12)', text: '#fb923c', bgLight: 'rgba(251,146,60,0.12)', textLight: '#fb923c' },
  MEDIUM:   { bg: 'rgba(250,204,21,0.1)',  text: '#facc15', bgLight: 'rgba(250,204,21,0.1)', textLight: '#facc15' },
  LOW:      { bg: 'rgba(96,165,250,0.1)',  text: '#60a5fa', bgLight: 'rgba(96,165,250,0.1)', textLight: '#60a5fa' },
}

const FALLBACK = { bg: 'rgba(148,163,184,0.1)', text: '#94a3b8', bgLight: 'rgba(148,163,184,0.1)', textLight: '#94a3b8' }

export default function SeverityBadge({ severity }) {
  const c = SEVERITY_CONFIG[severity] || FALLBACK
  const isLightMode = document.body.classList.contains('light-mode')
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-2 py-0.5"
      style={{ 
        background: isLightMode && severity === 'CRITICAL' ? c.bgLight : c.bg, 
        color: isLightMode && severity === 'CRITICAL' ? c.textLight : c.text, 
        fontSize: 11, 
        fontWeight: 600, 
        letterSpacing: '0.05em' 
      }}
    >
      {severity}
    </span>
  )
}
