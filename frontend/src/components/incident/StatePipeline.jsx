import { useMemo } from 'react'
import { Check } from 'lucide-react'

const STATE_ORDER = [
  { id: 'RECEIVED',             label: 'Received',     icon: '01' },
  { id: 'INVESTIGATING',        label: 'Investigating', icon: '02' },
  { id: 'RECOMMENDATION_READY', label: 'Analysis',      icon: '03' },
  { id: 'AWAITING_APPROVAL',    label: 'Approval',      icon: '04' },
  { id: 'EXECUTING',            label: 'Executing',     icon: '05' },
  { id: 'VERIFYING',            label: 'Verifying',     icon: '06' },
  { id: 'RESOLVED',             label: 'Resolved',      icon: '07' },
]

const COLORS = {
  normal:   { active: '#6366f1', done: 'rgba(99,102,241,0.2)', doneText: '#818cf8' },
  failed:   { active: '#f43f5e', done: 'rgba(244,63,94,0.2)',  doneText: '#fb7185' },
  escalated:{ active: '#f59e0b', done: 'rgba(245,158,11,0.2)', doneText: '#fbbf24' },
  resolved: { active: '#10b981', done: 'rgba(16,185,129,0.2)', doneText: '#34d399' },
}

export default function StatePipeline({ currentState }) {
  const currentIdx = useMemo(() => {
    const idx = STATE_ORDER.findIndex(s => s.id === currentState)
    if (idx !== -1) return idx
    if (currentState === 'FAILED_ANALYSIS') return 1
    if (currentState === 'FAILED_EXECUTION') return 4
    if (currentState === 'FAILED_VERIFICATION') return 5
    if (currentState === 'ESCALATED') return 6
    return 0
  }, [currentState])

  const isFailed = currentState?.includes('FAILED')
  const isEscalated = currentState === 'ESCALATED'
  const isResolved = currentState === 'RESOLVED'
  const palette = isFailed ? COLORS.failed : isEscalated ? COLORS.escalated : isResolved ? COLORS.resolved : COLORS.normal

  return (
    <div className="w-full overflow-x-auto py-2 px-2">
      <div className="flex items-center min-w-[600px]">
        {STATE_ORDER.map((step, i) => {
          const done = i < currentIdx
          const active = i === currentIdx

          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5 relative z-10">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center transition-all duration-500"
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    fontFamily: 'var(--font-mono)',
                    ...(done ? { background: palette.done, color: palette.doneText, border: `1px solid ${palette.doneText}40` } : {}),
                    ...(active ? { background: palette.active, color: '#fff', boxShadow: `0 0 12px ${palette.active}50`, transform: 'scale(1.1)' } : {}),
                    ...(!done && !active ? { background: 'var(--bg-input)', color: 'var(--text-muted)', border: '1px solid var(--border)' } : {}),
                  }}
                >
                  {done ? <Check size={14} strokeWidth={3} /> : step.icon}
                </div>
                <span style={{ fontSize: 10, fontWeight: 500, color: active ? 'var(--text-primary)' : 'var(--text-muted)', transition: 'color 0.3s' }}>
                  {step.label}
                </span>
              </div>
              {i < STATE_ORDER.length - 1 && (
                <div className="flex-1 h-[2px] mx-1.5 rounded-full relative overflow-hidden" style={{ background: 'var(--bg-input)' }}>
                  <div
                    className="absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out"
                    style={{ background: `${palette.active}60`, width: i < currentIdx ? '100%' : '0%' }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
