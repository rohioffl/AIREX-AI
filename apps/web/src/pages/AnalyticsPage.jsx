import { useState, useEffect } from 'react'
import { TrendingUp, BarChart3, Activity } from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { fetchAnalyticsTrends } from '../services/api'
import { formatDuration } from '../utils/formatters'

export default function AnalyticsPage() {
  const [days, setDays] = useState(30)
  const [trends, setTrends] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadTrends = async () => {
      setIsLoading(true)
      try {
        const data = await fetchAnalyticsTrends(days)
        setTrends(data)
      } catch (err) {
        console.error('Failed to load analytics trends:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadTrends()
  }, [days])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <TrendingUp size={24} style={{ color: '#22d3ee' }} />
            Analytics Dashboard
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Incident trends, resolution rates, and AI performance metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Period:</label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-border bg-input text-text-primary"
            style={{ fontSize: 13 }}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* MTTR Trends */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={18} className="text-cyan-400" />
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>MTTR Trends</h3>
        </div>
        {trends?.mttr_trends && trends.mttr_trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={trends.mttr_trends}>
              <defs>
                <linearGradient id="mttrGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="rgba(34,211,238,0.3)" />
                  <stop offset="95%" stopColor="transparent" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const data = payload[0].payload
                  return (
                    <div className="glass rounded-lg p-3 border border-border">
                      <p className="font-semibold text-text-heading mb-2">{data.date}</p>
                      <p className="text-sm text-text-secondary">
                        MTTR: {data.mttr_seconds ? formatDuration(data.mttr_seconds) : 'N/A'}
                      </p>
                      <p className="text-sm text-text-secondary">
                        Incidents: {data.incident_count}
                      </p>
                    </div>
                  )
                }}
              />
              <Area
                type="monotone"
                dataKey="mttr_seconds"
                stroke="#22d3ee"
                strokeWidth={2}
                fill="url(#mttrGradient)"
                name="MTTR (seconds)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center py-12 text-muted">No MTTR data available</div>
        )}
      </div>

      {/* Resolution Rates by Alert Type */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 size={18} className="text-indigo-400" />
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>Resolution Rates by Alert Type</h3>
        </div>
        {trends?.resolution_rates && trends.resolution_rates.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={trends.resolution_rates}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="alert_type" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} angle={-45} textAnchor="end" height={80} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const data = payload[0].payload
                  return (
                    <div className="glass rounded-lg p-3 border border-border">
                      <p className="font-semibold text-text-heading mb-2">{data.alert_type}</p>
                      <p className="text-sm text-text-secondary">
                        Resolution Rate: {(data.resolution_rate * 100).toFixed(1)}%
                      </p>
                      <p className="text-sm text-text-secondary">
                        Resolved: {data.resolved_count} / {data.total_incidents}
                      </p>
                    </div>
                  )
                }}
              />
              <Bar dataKey="resolution_rate" fill="#6366f1" name="Resolution Rate" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center py-12 text-muted">No resolution rate data available</div>
        )}
      </div>

      {/* AI Confidence Trends */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={18} className="text-purple-400" />
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>AI Confidence Trends</h3>
        </div>
        {trends?.ai_confidence_trends && trends.ai_confidence_trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends.ai_confidence_trends}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} domain={[0, 1]} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const data = payload[0].payload
                  return (
                    <div className="glass rounded-lg p-3 border border-border">
                      <p className="font-semibold text-text-heading mb-2">{data.date}</p>
                      <p className="text-sm text-text-secondary">
                        Avg Confidence: {data.avg_confidence ? `${(data.avg_confidence * 100).toFixed(1)}%` : 'N/A'}
                      </p>
                      <p className="text-sm text-text-secondary">
                        Incidents: {data.incident_count}
                      </p>
                    </div>
                  )
                }}
              />
              <Line
                type="monotone"
                dataKey="avg_confidence"
                stroke="#a855f7"
                strokeWidth={2}
                dot={{ fill: '#a855f7', r: 4 }}
                name="Avg Confidence"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center py-12 text-muted">No AI confidence data available</div>
        )}
      </div>
    </div>
  )
}
