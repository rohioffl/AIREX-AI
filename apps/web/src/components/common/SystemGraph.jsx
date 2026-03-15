import { useMemo, useState, useEffect, useRef } from 'react'
import { Activity } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts'

function formatHourLabel(d) {
  try {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', hour12: false }) + ':00'
  } catch {
    const h = String(d.getHours()).padStart(2, '0')
    return `${h}:00`
  }
}

function bucketStartOfHour(d) {
  const x = new Date(d)
  x.setMinutes(0, 0, 0)
  return x
}

function buildSeries(incidents) {
  const now = new Date()
  const end = bucketStartOfHour(now)
  const start = new Date(end)
  start.setHours(start.getHours() - 23)

  const buckets = []
  const byMs = new Map()

  for (let i = 0; i < 24; i++) {
    const b = new Date(start)
    b.setHours(start.getHours() + i)
    const key = b.getTime()
    const row = { name: formatHourLabel(b), incidents: 0, resolved: 0 }
    buckets.push(row)
    byMs.set(key, row)
  }

  const firstMs = buckets.length ? new Date(start).getTime() : 0
  const lastMs = new Date(end).getTime()

  for (const inc of incidents || []) {
    const created = inc?.created_at ? new Date(inc.created_at) : null
    if (created && !Number.isNaN(created.getTime())) {
      const ms = bucketStartOfHour(created).getTime()
      if (ms >= firstMs && ms <= lastMs) {
        const row = byMs.get(ms)
        if (row) row.incidents += 1
      }
    }

    if (inc?.state === 'RESOLVED' && inc?.updated_at) {
      const updated = new Date(inc.updated_at)
      if (!Number.isNaN(updated.getTime())) {
        const ms = bucketStartOfHour(updated).getTime()
        if (ms >= firstMs && ms <= lastMs) {
          const row = byMs.get(ms)
          if (row) row.resolved += 1
        }
      }
    }
  }

  return buckets
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass p-3 text-xs" style={{ minWidth: 140, background: 'rgba(17, 19, 24, 0.85)', backdropFilter: 'blur(12px)', border: '1px solid var(--border)' }}>
      <div style={{ fontWeight: 700, color: 'var(--text-heading)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-full pulse-ring" style={{ background: p.color, boxShadow: `0 0 8px ${p.color}` }} />
          <span style={{ color: 'var(--text-secondary)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function SystemGraph({ incidents = [], type = 'area' }) {
  const data = useMemo(() => buildSeries(incidents), [incidents])

  const containerRef = useRef(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    if (!containerRef.current) return
    const element = containerRef.current

    const updateSize = () => {
      const rect = element.getBoundingClientRect()
      const width = rect.width || 0
      const height = rect.height || 0
      if (width !== containerSize.width || height !== containerSize.height) {
        setContainerSize({ width, height })
      }
    }

    updateSize()

    const observer = new ResizeObserver(updateSize)
    observer.observe(element)

    return () => {
      observer.disconnect()
    }
  }, [containerSize.width, containerSize.height])

  const hasSize = containerSize.width > 0 && containerSize.height > 0

  const mini = useMemo(() => {
    const created24h = data.reduce((acc, r) => acc + (r.incidents || 0), 0)
    const resolved24h = data.reduce((acc, r) => acc + (r.resolved || 0), 0)
    const activeNow = (incidents || []).filter(i => !['RESOLVED', 'REJECTED'].includes(i.state)).length
    return [
      { label: 'Created (24h)', value: String(created24h) },
      { label: 'Resolved (24h)', value: String(resolved24h) },
      { label: 'Active Now', value: String(activeNow) },
    ]
  }, [data, incidents])

  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between mb-5 pb-3 divider-glow border-b-0">
        <div className="flex items-center gap-2">
          <Activity size={16} className="neon-text-cyan" />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
            {type === 'area' ? 'Incident Trend (24h)' : 'Resolution Rate'}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span className="w-2 h-2 rounded-full" style={{ background: 'var(--neon-indigo)', boxShadow: '0 0 6px rgba(99,102,241,0.5)' }} />
            Incidents
          </span>
          <span className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span className="w-2 h-2 rounded-full" style={{ background: 'var(--color-accent-green)', boxShadow: '0 0 6px rgba(16,185,129,0.5)' }} />
            Resolved
          </span>
        </div>
      </div>

      <div ref={containerRef} style={{ width: '100%', minHeight: 220, height: 220 }}>
        {hasSize && (
          <ResponsiveContainer width="100%" height="100%">
            {type === 'area' ? (
              <AreaChart data={data}>
              <defs>
                <linearGradient id="gradIncident" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="rgba(99,102,241,0.3)" />
                  <stop offset="95%" stopColor="transparent" />
                </linearGradient>
                <linearGradient id="gradResolved" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="rgba(16,185,129,0.3)" />
                  <stop offset="95%" stopColor="transparent" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--grid-line)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'var(--grid-line)', strokeWidth: 2, strokeDasharray: '4 4' }} />
              <Area type="monotone" dataKey="incidents" name="Incidents" stroke="var(--neon-indigo)" strokeWidth={2} fillOpacity={1} fill="url(#gradIncident)" activeDot={{ r: 4, style: { filter: 'drop-shadow(0 0 4px rgba(99,102,241,0.4))' } }} />
              <Area type="monotone" dataKey="resolved" name="Resolved" stroke="var(--color-accent-green)" strokeWidth={2} fillOpacity={1} fill="url(#gradResolved)" activeDot={{ r: 4, style: { filter: 'drop-shadow(0 0 4px rgba(16,185,129,0.4))' } }} />
            </AreaChart>
          ) : (
              <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--grid-line)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--bg-input)' }} />
              <Bar dataKey="incidents" name="Incidents" fill="var(--neon-indigo)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="resolved" name="Resolved" fill="var(--color-accent-green)" radius={[4, 4, 0, 0]} />
            </BarChart>
            )}
          </ResponsiveContainer>
        )}
      </div>

      {/* Mini stats */}
      <div className="flex gap-6 pt-4 mt-4 divider-glow border-t-0">
        {mini.map(s => (
          <div key={s.label} className="flex flex-col gap-1">
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{s.label}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
