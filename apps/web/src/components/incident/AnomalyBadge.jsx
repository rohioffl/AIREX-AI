import { AlertTriangle } from 'lucide-react'

const SEVERITY_THEME = {
  critical: { color: '#f43f5e', bg: 'rgba(244,63,94,0.08)', border: 'rgba(244,63,94,0.25)' },
  warning: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)' },
  info: { color: '#06b6d4', bg: 'rgba(6,182,212,0.08)', border: 'rgba(6,182,212,0.25)' },
}

export default function AnomalyBadge({ anomalies }) {
  if (!anomalies || anomalies.length === 0) return null

  const criticalCount = anomalies.filter(a => a.severity === 'critical').length
  const warningCount = anomalies.filter(a => a.severity === 'warning').length

  const overallSeverity = criticalCount > 0 ? 'critical' : warningCount > 0 ? 'warning' : 'info'
  const theme = SEVERITY_THEME[overallSeverity] || SEVERITY_THEME.info

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <AlertTriangle size={13} style={{ color: theme.color }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: theme.color, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {anomalies.length} Anomal{anomalies.length === 1 ? 'y' : 'ies'} Detected
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {anomalies.slice(0, 6).map((anomaly, idx) => {
          const t = SEVERITY_THEME[anomaly.severity] || SEVERITY_THEME.info
          return (
            <span
              key={idx}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: t.color,
                background: t.bg,
                border: `1px solid ${t.border}`,
              }}
              title={`${anomaly.metric_name}: ${anomaly.value} (threshold: ${anomaly.threshold})`}
            >
              {anomaly.description || anomaly.metric_name}
            </span>
          )
        })}
        {anomalies.length > 6 && (
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5"
            style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
          >
            +{anomalies.length - 6} more
          </span>
        )}
      </div>
    </div>
  )
}
