import { useState, useEffect, useCallback } from 'react'
import { Layers, TrendingUp, TrendingDown, Minus, AlertTriangle, Shield, Cpu } from 'lucide-react'
import { fetchPatterns, fetchAnomalies, predictRootCause, getPredictionAccuracy } from '../services/api'
import { useToasts } from '../context/ToastContext'
import { useNavigate } from 'react-router-dom'
import { useWorkspacePath } from '../hooks/useWorkspacePath'

const SEVERITY_STYLES = {
  CRITICAL: { background: 'rgba(244,63,94,0.12)', color: 'var(--color-accent-red)' },
  HIGH:     { background: 'rgba(251,146,60,0.12)', color: 'var(--brand-orange)' },
  MEDIUM:   { background: 'var(--glow-amber)', color: 'var(--color-accent-amber)' },
  LOW:      { background: 'rgba(16,185,129,0.12)', color: 'var(--neon-green)' },
}

const TREND_ICONS = {
  increasing:        { icon: TrendingUp,   color: 'var(--color-accent-red)', label: 'Increasing' },
  decreasing:        { icon: TrendingDown, color: 'var(--color-accent-green)', label: 'Decreasing' },
  stable:            { icon: Minus,        color: 'var(--text-muted)', label: 'Stable' },
  insufficient_data: { icon: Minus,        color: 'var(--text-muted)', label: 'N/A' },
}

const ANOMALY_BORDER = { high: 'var(--color-accent-red)', medium: 'var(--color-accent-amber)', low: 'var(--neon-cyan)' }
const ANOMALY_BADGE = {
  high:   { background: 'rgba(244,63,94,0.12)',  color: 'var(--color-accent-red)' },
  medium: { background: 'var(--glow-amber)', color: 'var(--color-accent-amber)' },
  low:    { background: 'rgba(59,130,246,0.12)',  color: 'var(--neon-cyan)' },
}

const card = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: 16,
}

function PatternCard({ pattern }) {
  const navigate = useNavigate()
  const { buildPath } = useWorkspacePath()
  const [expanded, setExpanded] = useState(false)
  const trend = TREND_ICONS[pattern.trend] || TREND_ICONS.stable
  const TrendIcon = trend.icon

  return (
    <div style={card}>
      <div className="flex items-start justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Layers size={16} style={{ color: 'var(--neon-indigo)' }} />
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-heading)' }}>{pattern.alert_type}</span>
            <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.12)', color: 'var(--neon-indigo)' }}>
              {pattern.incident_count} incidents
            </span>
            <span className="flex items-center gap-1" style={{ fontSize: 12, color: trend.color }}>
              <TrendIcon size={12} /> {trend.label}
            </span>
          </div>
          {pattern.root_cause && (
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              Root cause: <span style={{ fontWeight: 600 }}>{pattern.root_cause}</span>
            </p>
          )}
          <div className="flex items-center gap-4 mt-2" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            <span>{pattern.frequency_per_day}/day</span>
            {pattern.avg_resolution_seconds && (
              <span>Avg resolution: {Math.round(pattern.avg_resolution_seconds / 60)}m</span>
            )}
            <span>{pattern.affected_hosts?.length || 0} hosts</span>
          </div>
        </div>
        <div className="flex gap-1">
          {Object.entries(pattern.severity_distribution || {}).map(([sev, count]) => (
            <span key={sev} style={{ padding: '2px 6px', borderRadius: 4, fontSize: 11, ...(SEVERITY_STYLES[sev] || {}) }}>
              {sev}: {count}
            </span>
          ))}
        </div>
      </div>
      {expanded && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }} className="space-y-3">
          {pattern.common_actions && Object.keys(pattern.common_actions).length > 0 && (
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Common Actions</p>
              <div className="flex flex-wrap gap-1">
                {Object.entries(pattern.common_actions).map(([action, count]) => (
                  <span key={action} style={{ padding: '3px 8px', borderRadius: 6, fontSize: 12, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                    {action} ({count})
                  </span>
                ))}
              </div>
            </div>
          )}
          {pattern.incident_ids && pattern.incident_ids.length > 0 && (
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>Sample Incidents</p>
              <div className="flex flex-wrap gap-1">
                {pattern.incident_ids.slice(0, 5).map(id => (
                  <button key={id} onClick={() => navigate(buildPath(`incidents/${id}`))}
                    style={{ padding: '3px 8px', borderRadius: 6, fontSize: 12, fontFamily: 'var(--font-mono)', background: 'var(--glow-indigo)', color: 'var(--neon-indigo)', border: '1px solid rgba(99,102,241,0.2)', cursor: 'pointer' }}>
                    {id.slice(0, 8)}…
                  </button>
                ))}
              </div>
            </div>
          )}
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            First seen: {pattern.first_seen ? new Date(pattern.first_seen).toLocaleString() : 'N/A'}
            {' • '}
            Last seen: {pattern.last_seen ? new Date(pattern.last_seen).toLocaleString() : 'N/A'}
          </p>
        </div>
      )}
    </div>
  )
}

function AnomalyCard({ anomaly }) {
  const borderColor = ANOMALY_BORDER[anomaly.severity] || ANOMALY_BORDER.low
  const badge = ANOMALY_BADGE[anomaly.severity] || ANOMALY_BADGE.low

  return (
    <div style={{ ...card, borderLeft: `4px solid ${borderColor}`, paddingLeft: 14 }}>
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle size={15} style={{ color: borderColor }} />
        <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-heading)', textTransform: 'capitalize' }}>
          {anomaly.type.replace(/_/g, ' ')}
        </span>
        <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, ...badge }}>
          {anomaly.severity}
        </span>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{anomaly.description}</p>
    </div>
  )
}

function StatCard({ value, label }) {
  return (
    <div style={{ ...card, textAlign: 'center' }}>
      <p style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-heading)', fontFamily: 'var(--font-mono)' }}>{value}</p>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{label}</p>
    </div>
  )
}

export default function PatternsPage() {
  const [tab, setTab] = useState('patterns')
  const [patterns, setPatterns] = useState([])
  const [anomalies, setAnomalies] = useState(null)
  const [predictions, setPredictions] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [loading, setLoading] = useState(true)
  const [windowDays, setWindowDays] = useState(30)
  const [predAlertType, setPredAlertType] = useState('')
  const { addToast } = useToasts()

  const loadPatterns = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchPatterns(windowDays)
      setPatterns(data.patterns || [])
    } catch {
      addToast('Failed to load patterns', 'error')
    } finally {
      setLoading(false)
    }
  }, [windowDays, addToast])

  const loadAnomalies = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchAnomalies()
      setAnomalies(data)
    } catch {
      addToast('Failed to load anomalies', 'error')
    } finally {
      setLoading(false)
    }
  }, [addToast])

  const loadAccuracy = useCallback(async () => {
    try {
      const data = await getPredictionAccuracy()
      setAccuracy(data)
    } catch { /* silent */ }
  }, [])

  const handlePredict = async () => {
    if (!predAlertType.trim()) return
    try {
      setLoading(true)
      const data = await predictRootCause(predAlertType)
      setPredictions(data)
    } catch {
      addToast('Prediction failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (tab === 'patterns') loadPatterns()
    else if (tab === 'anomalies') loadAnomalies()
    else if (tab === 'predictions') loadAccuracy()
  }, [tab, loadPatterns, loadAnomalies, loadAccuracy])

  const tabs = [
    { id: 'patterns',    label: 'Patterns',    icon: Layers },
    { id: 'anomalies',   label: 'Anomalies',   icon: AlertTriangle },
    { id: 'predictions', label: 'Predictions', icon: Cpu },
  ]

  const inputStyle = {
    background: 'var(--bg-input)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--text-primary)',
    padding: '8px 12px',
    fontSize: 13,
    outline: 'none',
    width: '100%',
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>Proactive</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          Pattern detection, anomaly monitoring, and predictive analytics
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="flex items-center gap-2 flex-1 justify-center rounded-lg transition-all"
            style={{
              padding: '8px 16px',
              fontSize: 13,
              fontWeight: 600,
              background: tab === t.id ? 'var(--bg-card)' : 'transparent',
              color: tab === t.id ? 'var(--text-heading)' : 'var(--text-muted)',
              border: tab === t.id ? '1px solid var(--border)' : '1px solid transparent',
              boxShadow: tab === t.id ? 'var(--glass-shadow)' : 'none',
              cursor: 'pointer',
            }}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 rounded-full animate-spin" style={{ border: '3px solid var(--border)', borderTopColor: 'var(--neon-indigo)' }} />
        </div>
      )}

      {/* Patterns Tab */}
      {!loading && tab === 'patterns' && (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <select value={windowDays} onChange={(e) => setWindowDays(parseInt(e.target.value))}
              style={{ ...inputStyle, width: 'auto', paddingRight: 32 }}>
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{patterns.length} patterns detected</span>
          </div>
          {patterns.length === 0 ? (
            <div className="rounded-xl py-16 text-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <Layers size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', opacity: 0.5 }} />
              <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>No patterns detected in the selected time window</p>
            </div>
          ) : (
            <div className="space-y-3">
              {patterns.map(p => <PatternCard key={p.pattern_id} pattern={p} />)}
            </div>
          )}
        </div>
      )}

      {/* Anomalies Tab */}
      {!loading && tab === 'anomalies' && anomalies && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard value={anomalies.anomaly_count} label="Anomalies Detected" />
            <StatCard value={anomalies.recent_incident_count} label={`Recent Incidents (${anomalies.detection_window_hours}h)`} />
            <StatCard value={anomalies.baseline_incident_count} label={`Baseline (${anomalies.baseline_period_days}d)`} />
          </div>
          {anomalies.anomalies.length === 0 ? (
            <div className="rounded-xl py-12 text-center" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
              <Shield size={40} style={{ color: 'var(--color-accent-green)', margin: '0 auto 12px', opacity: 0.6 }} />
              <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>All Clear</p>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>No anomalies detected in the current window</p>
            </div>
          ) : (
            <div className="space-y-3">
              {anomalies.anomalies.map((a, idx) => <AnomalyCard key={idx} anomaly={a} />)}
            </div>
          )}
        </div>
      )}

      {/* Predictions Tab */}
      {!loading && tab === 'predictions' && (
        <div className="space-y-6">
          {accuracy && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard value={`${(accuracy.accuracy * 100).toFixed(1)}%`} label="Prediction Accuracy" />
              <StatCard value={`${accuracy.correct_predictions}/${accuracy.total_predictions}`} label="Correct / Total" />
              <StatCard value={accuracy.sample_size} label={`Sample Size (${accuracy.period_days}d)`} />
            </div>
          )}
          <div style={card}>
            <h3 style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-heading)', marginBottom: 16 }}>Predict Root Cause</h3>
            <div className="flex gap-3">
              <input type="text" value={predAlertType}
                onChange={(e) => setPredAlertType(e.target.value)}
                placeholder="Enter alert type (e.g., cpu_high, disk_full)"
                style={inputStyle}
                onKeyDown={(e) => e.key === 'Enter' && handlePredict()} />
              <button onClick={handlePredict} disabled={!predAlertType.trim()}
                style={{ padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: 'rgba(99,102,241,0.9)', color: '#fff', border: 'none', cursor: predAlertType.trim() ? 'pointer' : 'not-allowed', opacity: predAlertType.trim() ? 1 : 0.5, whiteSpace: 'nowrap' }}>
                Predict
              </button>
            </div>

            {predictions && (
              <div className="mt-6 space-y-4">
                {!predictions.prediction_available ? (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{predictions.message}</p>
                ) : (
                  <>
                    <div style={{ padding: 16, borderRadius: 10, background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)' }}>
                      <div className="flex items-center gap-2 mb-2">
                        <Cpu size={16} style={{ color: 'var(--neon-indigo)' }} />
                        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-heading)' }}>Top Prediction</span>
                        <span style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 700, color: 'var(--neon-indigo)' }}>
                          {(predictions.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                        <strong style={{ color: 'var(--text-heading)' }}>Root Cause:</strong> {predictions.top_prediction.root_cause}
                      </p>
                      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                        <strong style={{ color: 'var(--text-heading)' }}>Action:</strong> {predictions.top_prediction.recommended_action}
                      </p>
                      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                        Based on {predictions.historical_incident_count} historical incidents
                        {predictions.estimated_resolution_seconds && ` • Estimated resolution: ${Math.round(predictions.estimated_resolution_seconds / 60)} min`}
                      </p>
                    </div>
                    {predictions.all_predictions && predictions.all_predictions.length > 1 && (
                      <div>
                        <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>All Predictions</p>
                        <div className="space-y-2">
                          {predictions.all_predictions.map((p, idx) => (
                            <div key={idx} className="flex items-center gap-3 rounded-lg" style={{ padding: 12, background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                              <span style={{ width: 40, fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--neon-indigo)', textAlign: 'center' }}>
                                {(p.probability * 100).toFixed(0)}%
                              </span>
                              <div className="flex-1">
                                <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{p.root_cause}</p>
                                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.recommended_action} • {p.historical_count} occurrences</p>
                              </div>
                              <div style={{ width: 80, height: 6, borderRadius: 999, background: 'var(--bg-input)', overflow: 'hidden' }}>
                                <div style={{ width: `${p.probability * 100}%`, height: '100%', borderRadius: 999, background: 'var(--neon-indigo)' }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
