import { Loader, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'

const SHOW_STATES = new Set(['VERIFYING', 'RESOLVED', 'FAILED_VERIFICATION', 'ESCALATED'])

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
  ESCALATED: {
    border: '#f59e0b',
    bg: 'rgba(245,158,11,0.03)',
    Icon: AlertTriangle,
    iconClass: '',
    iconBg: 'rgba(245,158,11,0.1)',
    iconBorder: 'rgba(245,158,11,0.2)',
    iconColor: '#fbbf24',
    title: 'Escalated',
    titleColor: '#fbbf24',
    desc: 'Escalated to SRE on-call for manual resolution.',
  },
}

export default function VerificationResult({ state }) {
  if (!SHOW_STATES.has(state)) return null
  const c = CONFIGS[state]
  if (!c) return null

  return (
    <div className="glass rounded-xl flex items-start gap-4 p-5" style={{ borderLeft: `4px solid ${c.border}`, background: c.bg }}>
      <div className={`p-2 rounded-full ${c.iconClass}`} style={{ background: c.iconBg, border: `1px solid ${c.iconBorder}`, color: c.iconColor }}>
        <c.Icon size={18} />
      </div>
      <div>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: c.titleColor }}>{c.title}</h3>
        <p style={{ fontSize: 14, marginTop: 4, color: 'var(--text-secondary)' }}>{c.desc}</p>
      </div>
    </div>
  )
}
