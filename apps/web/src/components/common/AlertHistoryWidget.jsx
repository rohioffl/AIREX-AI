import { useMemo, useState, useEffect, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { fetchAlertHistory } from '../../services/api'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ minWidth: 140, background: 'rgba(17, 19, 24, 0.85)', backdropFilter: 'blur(12px)', border: '1px solid var(--border)', padding: '10px 12px', borderRadius: 8, fontSize: 12 }}>
      <div style={{ fontWeight: 700, color: 'var(--text-heading)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color, boxShadow: `0 0 8px ${p.color}` }} />
          <span style={{ color: 'var(--text-secondary)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function AlertHistoryWidget({ days = 7 }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const containerRef = useRef(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    let cancelled = false
    fetchAlertHistory({ days })
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [days])

  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current
    const update = () => {
      const rect = el.getBoundingClientRect()
      setContainerSize(prev =>
        rect.width !== prev.width || rect.height !== prev.height
          ? { width: rect.width, height: rect.height }
          : prev
      )
    }
    update()
    const obs = new ResizeObserver(update)
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const chartData = useMemo(() => {
    if (!data?.series) return []
    return data.series.map(d => ({
      name: d.date.slice(5),  // "MM-DD"
      alerts: d.alerts,
    }))
  }, [data])

  const mini = useMemo(() => {
    if (!data) return []
    const quietest = data.series?.length
      ? data.series.reduce((a, b) => a.alerts <= b.alerts ? a : b)
      : null
    return [
      { label: `Total Alerts (${days}d)`, value: String(data.total_alerts ?? 0) },
      { label: 'Most Affected', value: data.most_affected_monitor ?? '—' },
      { label: 'Quietest Day', value: quietest ? quietest.date.slice(5) : '—' },
    ]
  }, [data, days])

  const hasSize = containerSize.width > 0 && containerSize.height > 0

  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between mb-5 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} style={{ color: '#f59e0b' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
            Alert History ({days}d)
          </span>
        </div>
        <div className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          <span className="w-2 h-2 rounded-full" style={{ background: '#f59e0b', boxShadow: '0 0 6px rgba(245,158,11,0.5)' }} />
          Degraded / Down
        </div>
      </div>

      <div ref={containerRef} style={{ width: '100%', minHeight: 220, height: 220 }}>
        {loading ? (
          <div className="h-full skeleton rounded-lg" />
        ) : chartData.length === 0 || data?.total_alerts === 0 ? (
          <div className="h-full flex items-center justify-center">
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>No alert data yet — health checks will populate this once they run.</p>
          </div>
        ) : hasSize ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <defs>
                <linearGradient id="gradAlert" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="rgba(245,158,11,0.8)" />
                  <stop offset="95%" stopColor="rgba(245,158,11,0.3)" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--grid-line)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--bg-input)' }} />
              <Bar dataKey="alerts" name="Alerts" fill="url(#gradAlert)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : null}
      </div>

      <div className="flex gap-6 pt-4 mt-4" style={{ borderTop: '1px solid var(--border)' }}>
        {mini.map(s => (
          <div key={s.label} className="flex flex-col gap-1">
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{s.label}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)', fontFamily: s.label === 'Most Affected' ? 'inherit' : 'var(--font-mono)' }}>{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
