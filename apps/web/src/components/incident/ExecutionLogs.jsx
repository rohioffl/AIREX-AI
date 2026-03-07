import { useEffect, useRef } from 'react'
import Terminal from '../common/Terminal'
import { formatDuration } from '../../utils/formatters'

const SHOW_STATES = new Set([
  'EXECUTING', 'VERIFYING', 'RESOLVED',
  'FAILED_EXECUTION', 'FAILED_VERIFICATION',
])

export default function ExecutionLogs({ executions, state, liveLogs }) {
  const logsEndRef = useRef(null)

  useEffect(() => {
    if (state === 'EXECUTING') {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [liveLogs, state])

  if (!SHOW_STATES.has(state)) return null

  return (
    <div className="space-y-3">
      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Execution Log</span>

      {executions?.map((exec) => (
        <div key={exec.id} className="glass rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5" style={{ background: 'var(--bg-input)' }}>
            <div className="flex items-center gap-2">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#818cf8' }}>{exec.action_type}</span>
              <span className="px-1.5 py-0.5 rounded" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-input)' }}>
                #{exec.attempt}
              </span>
            </div>
            <div className="flex items-center gap-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              <span style={{ color: exec.status === 'COMPLETED' ? '#34d399' : exec.status === 'FAILED' ? '#fb7185' : '#38bdf8' }}>
                {exec.status}
              </span>
              {exec.duration_seconds != null && (
                <span style={{ color: 'var(--text-muted)' }}>{formatDuration(exec.duration_seconds)}</span>
              )}
            </div>
          </div>
          {exec.logs && (
            <Terminal content={exec.logs} hostname={exec.action_type} maxHeight={200} />
          )}
        </div>
      ))}

      {liveLogs && liveLogs.length > 0 && (
        <div className="glass rounded-lg overflow-hidden" style={{ borderLeft: '2px solid rgba(16,185,129,0.5)' }}>
          <div className="px-4 py-2 flex items-center gap-2" style={{ background: 'rgba(16,185,129,0.03)' }}>
            <span className="h-2 w-2 rounded-full animate-pulse" style={{ background: '#34d399' }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Live</span>
          </div>
          <Terminal content={liveLogs.join('\n')} hostname="live-exec" maxHeight={200} />
          <div ref={logsEndRef} />
        </div>
      )}
    </div>
  )
}
