import { useMemo } from 'react'
import { Activity } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts'

function generateData(incidents) {
  const hours = 24
  const data = []
  for (let i = 0; i < hours; i++) {
    const hr = String(i).padStart(2, '0') + ':00'
    data.push({
      name: hr,
      incidents: Math.floor(Math.random() * 4) + (incidents.length > 5 ? 2 : 0),
      resolved: Math.floor(Math.random() * 3),
      responseTime: Math.floor(Math.random() * 40) + 10,
    })
  }
  return data
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass p-3 text-xs" style={{ minWidth: 140 }}>
      <div style={{ fontWeight: 700, color: 'var(--text-heading)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span style={{ color: 'var(--text-secondary)' }}>{p.name}:</span>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function SystemGraph({ incidents = [], type = 'area' }) {
  const data = useMemo(() => generateData(incidents), [incidents.length])

  return (
    <div className="glass p-5">
      <div className="flex items-center justify-between mb-5 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <Activity size={16} style={{ color: '#22d3ee' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
            {type === 'area' ? 'Incident Trend (24h)' : 'Resolution Rate'}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span className="w-2 h-2 rounded-full" style={{ background: '#6366f1' }} />
            Incidents
          </span>
          <span className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span className="w-2 h-2 rounded-full" style={{ background: '#10b981' }} />
            Resolved
          </span>
        </div>
      </div>

      <div style={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          {type === 'area' ? (
            <AreaChart data={data}>
              <defs>
                <linearGradient id="gradIncident" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradResolved" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="incidents" name="Incidents" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#gradIncident)" />
              <Area type="monotone" dataKey="resolved" name="Resolved" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#gradResolved)" />
            </AreaChart>
          ) : (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="incidents" name="Incidents" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="resolved" name="Resolved" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Mini stats */}
      <div className="flex gap-6 pt-4 mt-4" style={{ borderTop: '1px solid var(--border)' }}>
        {[
          { label: 'Avg Response', value: '23ms' },
          { label: 'Uptime', value: '99.97%' },
          { label: 'Active Nodes', value: '14/14' },
        ].map(s => (
          <div key={s.label} className="flex flex-col gap-1">
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{s.label}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
