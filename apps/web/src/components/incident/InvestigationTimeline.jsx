import { useState } from 'react'
import { Activity, CheckCircle2, XCircle, Loader, AlertTriangle, Clock } from 'lucide-react'

const STATUS_CONFIG = {
  started: { icon: Loader, color: 'var(--neon-cyan)', iconClass: 'animate-spin', label: 'Running' },
  completed: { icon: CheckCircle2, color: 'var(--color-accent-green)', iconClass: '', label: 'Done' },
  failed: { icon: XCircle, color: 'var(--color-accent-red)', iconClass: '', label: 'Failed' },
  anomalies_detected: { icon: AlertTriangle, color: 'var(--color-accent-amber)', iconClass: '', label: 'Anomalies' },
}

const CATEGORY_COLORS = {
  primary: 'var(--neon-indigo)',
  monitoring: 'var(--neon-cyan)',
  change: 'var(--color-accent-amber)',
  infrastructure: 'var(--neon-purple)',
  log_analysis: 'var(--color-accent-green)',
  secondary: 'var(--text-muted)',
}

export default function InvestigationTimeline({ probeSteps }) {
  const [expanded, setExpanded] = useState(true)

  if (!probeSteps || probeSteps.length === 0) return null

  const completedCount = probeSteps.filter(s => s.status === 'completed' || s.status === 'anomalies_detected').length
  const totalSteps = probeSteps[0]?.total_steps || probeSteps.length
  const allDone = completedCount >= totalSteps || probeSteps.every(s => s.status !== 'started')
  const hasAnomalies = probeSteps.some(s => s.anomaly_count > 0)

  return (
    <div className="glass rounded-xl overflow-hidden" style={{ borderLeft: '4px solid var(--neon-indigo)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-5 py-4 w-full text-left transition-colors"
        style={{ background: 'transparent' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-md flex items-center justify-center"
            style={{ background: 'rgba(129,140,248,0.1)', color: 'var(--neon-indigo)' }}
          >
            <Activity size={16} />
          </div>
          <div>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Investigation Progress
            </h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {allDone ? `${completedCount} probes completed` : `${completedCount}/${totalSteps} probes`}
              {hasAnomalies && ' \u2022 anomalies detected'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {!allDone && (
            <div className="h-2 rounded-full overflow-hidden" style={{ width: 80, background: 'rgba(148,163,184,0.2)' }}>
              <div
                className="h-full transition-all"
                style={{
                  width: `${totalSteps > 0 ? (completedCount / totalSteps) * 100 : 0}%`,
                  background: 'var(--neon-indigo)',
                }}
              />
            </div>
          )}
          <span style={{
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s',
          }}>
            \u25BC
          </span>
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-1">
          {probeSteps.map((step, idx) => {
            const cfg = STATUS_CONFIG[step.status] || STATUS_CONFIG.started
            const Icon = cfg.icon
            const catColor = CATEGORY_COLORS[step.category] || CATEGORY_COLORS.secondary

            return (
              <div
                key={`${step.probe_name}-${idx}`}
                className="flex items-center gap-3 py-2 px-3 rounded-lg"
                style={{
                  background: step.status === 'started' ? 'rgba(34,211,238,0.03)' : 'transparent',
                  borderLeft: `2px solid ${cfg.color}`,
                }}
              >
                <div className={cfg.iconClass} style={{ color: cfg.color, flexShrink: 0 }}>
                  <Icon size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {step.probe_name}
                    </span>
                    {step.category && (
                      <span
                        className="px-1.5 py-0.5 rounded"
                        style={{ fontSize: 9, fontWeight: 600, color: catColor, background: `${catColor}15`, border: `1px solid ${catColor}30` }}
                      >
                        {step.category}
                      </span>
                    )}
                  </div>
                  {step.anomaly_count > 0 && (
                    <span style={{ fontSize: 10, color: 'var(--color-accent-amber)', fontWeight: 600 }}>
                      {step.anomaly_count} anomal{step.anomaly_count === 1 ? 'y' : 'ies'} detected
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {step.duration_ms > 0 && (
                    <span className="flex items-center gap-1" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                      <Clock size={10} />
                      {step.duration_ms < 1000 ? `${Math.round(step.duration_ms)}ms` : `${(step.duration_ms / 1000).toFixed(1)}s`}
                    </span>
                  )}
                  <span style={{ fontSize: 10, fontWeight: 600, color: cfg.color }}>
                    {cfg.label}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
