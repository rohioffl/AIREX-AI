import { useState, useEffect } from 'react'
import { Activity, TrendingUp, AlertCircle, Clock } from 'lucide-react'
import api from '../../services/api'

export default function Site24x7MetricsPanel({ incident }) {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Extract monitor_id from incident meta
  const monitorId = incident?.meta?.MONITORID || incident?.meta?.monitor_id

  useEffect(() => {
    if (!monitorId) return

    const loadMetrics = async () => {
      setLoading(true)
      setError(null)
      try {
        const [summary, performance, outages] = await Promise.all([
          api.get(`/site24x7/monitors/${monitorId}/summary`).catch(() => null),
          api.get(`/site24x7/monitors/${monitorId}/performance?period=1`).catch(() => null),
          api.get(`/site24x7/monitors/${monitorId}/outages?period=3`).catch(() => null),
        ])

        setMetrics({
          summary: summary?.data || null,
          performance: performance?.data || null,
          outages: outages?.data || null,
        })
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    loadMetrics()
  }, [monitorId])

  if (!monitorId) {
    return null // Don't show panel if no monitor ID
  }

  if (loading) {
    return (
      <div className="glass rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={18} style={{ color: 'var(--neon-indigo)' }} />
          <h3 className="font-semibold" style={{ color: 'var(--text-heading)' }}>
            Site24x7 Metrics
          </h3>
        </div>
        <div className="text-sm text-muted">Loading metrics...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle size={18} className="text-red-500" />
          <h3 className="font-semibold" style={{ color: 'var(--text-heading)' }}>
            Site24x7 Metrics
          </h3>
        </div>
        <div className="text-sm text-red-500">Failed to load: {error}</div>
      </div>
    )
  }

  if (!metrics) {
    return null
  }

  const perf = metrics.performance?.response_time || {}
  const outages = metrics.outages || {}
  const status = metrics.summary?.current_status || {}

  return (
    <div className="glass rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <Activity size={18} style={{ color: 'var(--neon-indigo)' }} />
        <h3 className="font-semibold" style={{ color: 'var(--text-heading)' }}>
          Site24x7 Monitor Metrics
        </h3>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {status.status_name && (
          <div>
            <div className="text-xs text-muted mb-1">Current Status</div>
            <div className="font-medium">{status.status_name}</div>
          </div>
        )}

        {perf.average && (
          <div>
            <div className="text-xs text-muted mb-1 flex items-center gap-1">
              <TrendingUp size={12} />
              Avg Response Time
            </div>
            <div className="font-medium">{perf.average}ms</div>
          </div>
        )}

        {perf.max && (
          <div>
            <div className="text-xs text-muted mb-1">Max Response Time</div>
            <div className="font-medium">{perf.max}ms</div>
          </div>
        )}

        {outages.no_of_outages !== undefined && (
          <div>
            <div className="text-xs text-muted mb-1 flex items-center gap-1">
              <Clock size={12} />
              Outages (30d)
            </div>
            <div className="font-medium">{outages.no_of_outages}</div>
          </div>
        )}
      </div>

      {outages.no_of_outages > 5 && (
        <div className="mt-4 p-3 rounded-lg" style={{ background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.3)' }}>
          <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-accent-amber)' }}>
            <AlertCircle size={16} />
            <span>⚠️ Frequent outages detected - recurring issue pattern</span>
          </div>
        </div>
      )}
    </div>
  )
}
