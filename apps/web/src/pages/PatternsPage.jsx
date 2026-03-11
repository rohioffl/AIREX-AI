import { useState, useEffect, useCallback } from 'react'
import { Layers, TrendingUp, TrendingDown, Minus, AlertTriangle, Activity, Eye, Shield, Cpu, BarChart3 } from 'lucide-react'
import { fetchPatterns, fetchAnomalies, predictRootCause, getPredictionAccuracy } from '../services/api'
import { useToasts } from '../context/ToastContext'
import { useNavigate } from 'react-router-dom'

const SEVERITY_COLORS = {
  CRITICAL: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  HIGH: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  MEDIUM: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  LOW: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
}

const TREND_ICONS = {
  increasing: { icon: TrendingUp, color: 'text-red-500', label: 'Increasing' },
  decreasing: { icon: TrendingDown, color: 'text-green-500', label: 'Decreasing' },
  stable: { icon: Minus, color: 'text-gray-500', label: 'Stable' },
  insufficient_data: { icon: Minus, color: 'text-gray-400', label: 'N/A' },
}

function PatternCard({ pattern }) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const trend = TREND_ICONS[pattern.trend] || TREND_ICONS.stable
  const TrendIcon = trend.icon

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4">
      <div className="flex items-start justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-4 h-4 text-blue-500" />
            <h3 className="font-semibold dark:text-white text-sm">{pattern.alert_type}</h3>
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full text-xs">
              {pattern.incident_count} incidents
            </span>
            <div className={`flex items-center gap-1 ${trend.color}`}>
              <TrendIcon className="w-3.5 h-3.5" />
              <span className="text-xs">{trend.label}</span>
            </div>
          </div>
          {pattern.root_cause && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Root cause: <span className="font-medium">{pattern.root_cause}</span>
            </p>
          )}
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
            <span>{pattern.frequency_per_day}/day</span>
            {pattern.avg_resolution_seconds && (
              <span>Avg resolution: {Math.round(pattern.avg_resolution_seconds / 60)}m</span>
            )}
            <span>{pattern.affected_hosts?.length || 0} hosts</span>
          </div>
        </div>
        <div className="flex gap-1">
          {Object.entries(pattern.severity_distribution || {}).map(([sev, count]) => (
            <span key={sev} className={`px-1.5 py-0.5 rounded text-xs ${SEVERITY_COLORS[sev] || ''}`}>
              {sev}: {count}
            </span>
          ))}
        </div>
      </div>
      {expanded && (
        <div className="mt-3 pt-3 border-t dark:border-gray-700 space-y-3">
          {pattern.common_actions && Object.keys(pattern.common_actions).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Common Actions</h4>
              <div className="flex flex-wrap gap-1">
                {Object.entries(pattern.common_actions).map(([action, count]) => (
                  <span key={action} className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-xs dark:text-gray-300">
                    {action} ({count})
                  </span>
                ))}
              </div>
            </div>
          )}
          {pattern.incident_ids && pattern.incident_ids.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Sample Incidents</h4>
              <div className="flex flex-wrap gap-1">
                {pattern.incident_ids.slice(0, 5).map(id => (
                  <button key={id} onClick={() => navigate(`/incidents/${id}`)}
                    className="px-2 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded text-xs hover:bg-blue-100 dark:hover:bg-blue-900/40 font-mono">
                    {id.slice(0, 8)}...
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="text-xs text-gray-400">
            First seen: {pattern.first_seen ? new Date(pattern.first_seen).toLocaleString() : 'N/A'}
            {' • '}
            Last seen: {pattern.last_seen ? new Date(pattern.last_seen).toLocaleString() : 'N/A'}
          </div>
        </div>
      )}
    </div>
  )
}

function AnomalyCard({ anomaly }) {
  const severityColor = anomaly.severity === 'high' ? 'border-red-500 bg-red-50 dark:bg-red-900/10' :
    anomaly.severity === 'medium' ? 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/10' :
    'border-blue-500 bg-blue-50 dark:bg-blue-900/10'

  return (
    <div className={`rounded-lg border-l-4 p-4 ${severityColor}`}>
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle className={`w-4 h-4 ${anomaly.severity === 'high' ? 'text-red-500' : anomaly.severity === 'medium' ? 'text-yellow-500' : 'text-blue-500'}`} />
        <span className="font-medium text-sm dark:text-white capitalize">{anomaly.type.replace(/_/g, ' ')}</span>
        <span className={`px-2 py-0.5 rounded-full text-xs ${anomaly.severity === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : anomaly.severity === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'}`}>
          {anomaly.severity}
        </span>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-400">{anomaly.description}</p>
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
    } catch (err) {
      addToast('Failed to load patterns', 'error')
    } finally {
      setLoading(false)
    }
  }, [windowDays])

  const loadAnomalies = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchAnomalies()
      setAnomalies(data)
    } catch (err) {
      addToast('Failed to load anomalies', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadAccuracy = useCallback(async () => {
    try {
      const data = await getPredictionAccuracy()
      setAccuracy(data)
    } catch {}
  }, [])

  const handlePredict = async () => {
    if (!predAlertType.trim()) return
    try {
      setLoading(true)
      const data = await predictRootCause(predAlertType)
      setPredictions(data)
    } catch (err) {
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
    { id: 'patterns', label: 'Patterns', icon: Layers },
    { id: 'anomalies', label: 'Anomalies', icon: AlertTriangle },
    { id: 'predictions', label: 'Predictions', icon: Cpu },
  ]

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold dark:text-white">AI Intelligence</h1>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
          Pattern detection, anomaly monitoring, and predictive analytics
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors flex-1 justify-center
              ${tab === t.id ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Patterns Tab */}
      {!loading && tab === 'patterns' && (
        <div>
          <div className="flex items-center gap-4 mb-4">
            <select value={windowDays} onChange={(e) => setWindowDays(parseInt(e.target.value))}
              className="px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm">
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <span className="text-sm text-gray-500 dark:text-gray-400">{patterns.length} patterns detected</span>
          </div>
          {patterns.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <Layers className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No patterns detected in the selected time window</p>
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
        <div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold dark:text-white">{anomalies.anomaly_count}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Anomalies Detected</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold dark:text-white">{anomalies.recent_incident_count}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Recent Incidents ({anomalies.detection_window_hours}h)</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 text-center">
              <p className="text-2xl font-bold dark:text-white">{anomalies.baseline_incident_count}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Baseline ({anomalies.baseline_period_days}d)</p>
            </div>
          </div>
          {anomalies.anomalies.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <Shield className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">All Clear</p>
              <p className="text-sm mt-1">No anomalies detected in the current window</p>
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
              <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 text-center">
                <p className="text-2xl font-bold dark:text-white">{(accuracy.accuracy * 100).toFixed(1)}%</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Prediction Accuracy</p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 text-center">
                <p className="text-2xl font-bold dark:text-white">{accuracy.correct_predictions}/{accuracy.total_predictions}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Correct/Total</p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 text-center">
                <p className="text-2xl font-bold dark:text-white">{accuracy.sample_size}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Sample Size ({accuracy.period_days}d)</p>
              </div>
            </div>
          )}

          <div className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-6">
            <h3 className="font-semibold dark:text-white mb-4">Predict Root Cause</h3>
            <div className="flex gap-3">
              <input type="text" value={predAlertType} onChange={(e) => setPredAlertType(e.target.value)}
                placeholder="Enter alert type (e.g., cpu_high, disk_full)" 
                className="flex-1 px-3 py-2 rounded border dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                onKeyDown={(e) => e.key === 'Enter' && handlePredict()} />
              <button onClick={handlePredict} disabled={!predAlertType.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                Predict
              </button>
            </div>

            {predictions && (
              <div className="mt-6 space-y-4">
                {!predictions.prediction_available ? (
                  <p className="text-gray-500 dark:text-gray-400">{predictions.message}</p>
                ) : (
                  <>
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                      <div className="flex items-center gap-2 mb-2">
                        <Cpu className="w-5 h-5 text-blue-600" />
                        <h4 className="font-semibold dark:text-white">Top Prediction</h4>
                        <span className="ml-auto text-sm font-bold text-blue-600">{(predictions.confidence * 100).toFixed(0)}% confidence</span>
                      </div>
                      <p className="dark:text-gray-300"><strong>Root Cause:</strong> {predictions.top_prediction.root_cause}</p>
                      <p className="dark:text-gray-300"><strong>Action:</strong> {predictions.top_prediction.recommended_action}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Based on {predictions.historical_incident_count} historical incidents
                        {predictions.estimated_resolution_seconds && ` • Estimated resolution: ${Math.round(predictions.estimated_resolution_seconds / 60)} min`}
                      </p>
                    </div>
                    {predictions.all_predictions && predictions.all_predictions.length > 1 && (
                      <div>
                        <h4 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">All Predictions</h4>
                        <div className="space-y-2">
                          {predictions.all_predictions.map((p, idx) => (
                            <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded">
                              <div className="w-12 text-center">
                                <span className="text-sm font-bold dark:text-white">{(p.probability * 100).toFixed(0)}%</span>
                              </div>
                              <div className="flex-1">
                                <p className="text-sm font-medium dark:text-white">{p.root_cause}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">{p.recommended_action} • {p.historical_count} occurrences</p>
                              </div>
                              <div className="w-24 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                                <div className="bg-blue-500 rounded-full h-2" style={{ width: `${p.probability * 100}%` }} />
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
