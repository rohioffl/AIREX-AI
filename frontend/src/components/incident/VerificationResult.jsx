import { Loader, CheckCircle, XCircle, ClipboardCheck } from 'lucide-react'

const SHOW_STATES = new Set(['VERIFYING', 'RESOLVED', 'FAILED_VERIFICATION'])

const CONFIGS = {
  VERIFYING: {
    border: '#22d3ee',
    bg: 'rgba(34,211,238,0.03)',
    Icon: Loader,
    iconClass: 'animate-spin',
    iconBg: 'rgba(34,211,238,0.1)',
    iconBorder: 'rgba(34,211,238,0.2)',
    iconColor: '#22d3ee',
    title: 'Verifying Fix',
    titleColor: '#22d3ee',
    desc: 'Running post-execution health checks...',
  },
  RESOLVED: {
    border: '#10b981',
    bg: 'rgba(16,185,129,0.03)',
    Icon: CheckCircle,
    iconClass: '',
    iconBg: 'rgba(16,185,129,0.1)',
    iconBorder: 'rgba(16,185,129,0.2)',
    iconColor: '#34d399',
    title: 'Incident Resolved',
    titleColor: '#34d399',
    desc: 'Verification passed. Normal operations restored.',
  },
  FAILED_VERIFICATION: {
    border: '#f43f5e',
    bg: 'rgba(244,63,94,0.03)',
    Icon: XCircle,
    iconClass: '',
    iconBg: 'rgba(244,63,94,0.1)',
    iconBorder: 'rgba(244,63,94,0.2)',
    iconColor: '#fb7185',
    title: 'Verification Failed',
    titleColor: '#fb7185',
    desc: 'System still reporting issues. Manual intervention may be required.',
  },
}

export default function VerificationResult({ state, incident }) {
  if (!SHOW_STATES.has(state)) return null
  const c = CONFIGS[state]
  if (!c) return null

  const recommendation = incident?.recommendation || incident?.meta?.recommendation
  const verificationCriteria = recommendation?.verification_criteria || []
  const isResolved = state === 'RESOLVED'

  return (
    <div className="glass rounded-xl p-5 space-y-4" style={{ borderLeft: `4px solid ${c.border}`, background: c.bg }}>
      <div className="flex items-start gap-4">
        <div className={`p-2 rounded-full ${c.iconClass}`} style={{ background: c.iconBg, border: `1px solid ${c.iconBorder}`, color: c.iconColor }}>
          <c.Icon size={18} />
        </div>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: c.titleColor }}>{c.title}</h3>
          <p style={{ fontSize: 14, marginTop: 4, color: 'var(--text-secondary)' }}>{c.desc}</p>
        </div>
      </div>

      {verificationCriteria.length > 0 && (
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2 mb-3">
            <ClipboardCheck size={14} style={{ color: c.iconColor }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Verification Criteria
            </span>
          </div>
          <ul className="space-y-2">
            {verificationCriteria.map((criterion, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2 py-1"
                style={{ fontSize: 12, color: 'var(--text-secondary)' }}
              >
                <span style={{ color: isResolved ? '#10b981' : c.iconColor, flexShrink: 0, marginTop: 2 }}>
                  {isResolved ? '\u2713' : '\u25CB'}
                </span>
                <span>{criterion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
