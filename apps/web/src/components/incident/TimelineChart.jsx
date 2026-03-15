import { useMemo, useState } from 'react'
import { ZoomIn, ZoomOut, Filter } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { formatTimestamp } from '../../utils/formatters'

/**
 * TimelineChart - Visual timeline of incident state transitions with zoom/filter capabilities.
 */
export default function TimelineChart({ transitions, incidentCreatedAt, incidentResolvedAt }) {
  const [zoomLevel, setZoomLevel] = useState(1)
  const [filterStates, setFilterStates] = useState(new Set())

  // Build chart data from transitions
  const chartData = useMemo(() => {
    if (!transitions || transitions.length === 0) return []

    const data = []
    let cumulativeTime = 0

    for (let i = 0; i < transitions.length; i++) {
      const trans = transitions[i]
      const prevTime = i === 0 
        ? new Date(incidentCreatedAt || trans.created_at).getTime()
        : new Date(transitions[i - 1].created_at).getTime()
      const currentTime = new Date(trans.created_at).getTime()
      const duration = (currentTime - prevTime) / 1000 // seconds

      cumulativeTime += duration

      if (filterStates.size === 0 || filterStates.has(trans.to_state)) {
        data.push({
          timestamp: trans.created_at,
          time: cumulativeTime,
          from_state: trans.from_state,
          to_state: trans.to_state,
          state: trans.to_state,
          reason: trans.reason || '',
          actor: trans.actor || 'system',
        })
      }
    }

    // Add resolved point if incident is resolved
    if (incidentResolvedAt && transitions.length > 0) {
      const lastTrans = transitions[transitions.length - 1]
      const lastTime = new Date(lastTrans.created_at).getTime()
      const resolvedTime = new Date(incidentResolvedAt).getTime()
      const finalDuration = (resolvedTime - lastTime) / 1000
      const totalTime = data.length > 0 ? data[data.length - 1].time + finalDuration : finalDuration

      data.push({
        timestamp: incidentResolvedAt,
        time: totalTime,
        from_state: lastTrans.to_state,
        to_state: 'RESOLVED',
        state: 'RESOLVED',
        reason: 'Incident resolved',
        actor: 'system',
      })
    }

    return data
  }, [transitions, incidentCreatedAt, incidentResolvedAt, filterStates])

  const allStates = useMemo(() => {
    const states = new Set()
    if (transitions) {
      transitions.forEach(t => {
        states.add(t.from_state)
        states.add(t.to_state)
      })
    }
    return Array.from(states).sort()
  }, [transitions])

  const handleToggleState = (state) => {
    setFilterStates(prev => {
      const next = new Set(prev)
      if (next.has(state)) {
        next.delete(state)
      } else {
        next.add(state)
      }
      return next
    })
  }

  if (!transitions || transitions.length === 0) {
    return (
      <div className="glass rounded-xl p-6 text-center text-muted">
        No timeline data available
      </div>
    )
  }

  return (
    <div className="glass rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-indigo-400" />
          <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>
            State Transition Timeline
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoomLevel(prev => Math.max(0.5, prev - 0.25))}
            className="p-1.5 rounded-lg hover:bg-input transition-colors"
            title="Zoom out"
          >
            <ZoomOut size={14} className="text-muted" />
          </button>
          <span className="text-xs text-muted" style={{ minWidth: 60, textAlign: 'center' }}>
            {Math.round(zoomLevel * 100)}%
          </span>
          <button
            onClick={() => setZoomLevel(prev => Math.min(2, prev + 0.25))}
            className="p-1.5 rounded-lg hover:bg-input transition-colors"
            title="Zoom in"
          >
            <ZoomIn size={14} className="text-muted" />
          </button>
        </div>
      </div>

      {/* State filter */}
      <div className="flex flex-wrap gap-2">
        {allStates.map(state => (
          <button
            key={state}
            onClick={() => handleToggleState(state)}
            className="px-2 py-1 rounded text-xs font-semibold transition-all"
            style={{
              background: filterStates.size === 0 || filterStates.has(state)
                ? 'rgba(99,102,241,0.15)'
                : 'var(--bg-input)',
              color: filterStates.size === 0 || filterStates.has(state)
                ? 'var(--neon-indigo)'
                : 'var(--text-muted)',
              border: `1px solid ${filterStates.size === 0 || filterStates.has(state) ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
              opacity: filterStates.size > 0 && !filterStates.has(state) ? 0.4 : 1,
            }}
          >
            {state}
          </button>
        ))}
        {filterStates.size > 0 && (
          <button
            onClick={() => setFilterStates(new Set())}
            className="px-2 py-1 rounded text-xs font-semibold transition-all"
            style={{
              background: 'var(--bg-input)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="time"
              type="number"
              scale="linear"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
              label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -5, style: { fontSize: 11, fill: 'var(--text-muted)' } }}
            />
            <YAxis
              dataKey="state"
              type="category"
              tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
              width={120}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const data = payload[0].payload
                return (
                  <div className="glass rounded-lg p-3 border border-border">
                    <p className="font-semibold text-text-heading mb-2">{data.state}</p>
                    <p className="text-xs text-text-secondary mb-1">
                      From: {data.from_state}
                    </p>
                    <p className="text-xs text-text-secondary mb-1">
                      Time: {data.time.toFixed(1)}s
                    </p>
                    <p className="text-xs text-text-secondary mb-1">
                      {formatTimestamp(data.timestamp)}
                    </p>
                    {data.reason && (
                      <p className="text-xs text-text-secondary mt-2 pt-2 border-t border-border">
                        {data.reason}
                      </p>
                    )}
                  </div>
                )
              }}
            />
            <Line
              type="stepAfter"
              dataKey="state"
              stroke="var(--neon-indigo)"
              strokeWidth={2}
              dot={{ fill: 'var(--neon-indigo)', r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
