import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, Radio, Pause, Play, Trash2, ChevronRight, ArrowDown
} from 'lucide-react'
import { createSSEConnection } from '../services/sse'
import ConnectionBanner from '../components/common/ConnectionBanner'
import StateBadge from '../components/common/StateBadge'
import SeverityBadge from '../components/common/SeverityBadge'
import { truncateId } from '../utils/formatters'

const EVENT_COLORS = {
  incident_created:     { bg: 'rgba(96,165,250,0.08)',  accent: '#60a5fa', label: 'INCIDENT' },
  state_changed:        { bg: 'rgba(167,139,250,0.08)', accent: '#a78bfa', label: 'STATE' },
  evidence_added:       { bg: 'rgba(52,211,153,0.08)',  accent: '#34d399', label: 'EVIDENCE' },
  recommendation_ready: { bg: 'rgba(251,191,36,0.08)',  accent: '#fbbf24', label: 'AI REC' },
  execution_started:    { bg: 'rgba(56,189,248,0.08)',  accent: '#38bdf8', label: 'EXEC' },
  execution_log:        { bg: 'rgba(148,163,184,0.06)', accent: '#94a3b8', label: 'LOG' },
  execution_completed:  { bg: 'rgba(34,211,238,0.08)',  accent: '#22d3ee', label: 'DONE' },
  verification_result:  { bg: 'rgba(52,211,153,0.08)',  accent: '#34d399', label: 'VERIFY' },
}

export default function LiveFeed() {
  const [events, setEvents] = useState([])
  const [paused, setPaused] = useState(false)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [initial, setInitial] = useState(true)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('all')
  const feedRef = useRef(null)
  const pausedRef = useRef(paused)

  pausedRef.current = paused

  useEffect(() => {
    const handlers = {}
    const eventTypes = [
      'incident_created', 'state_changed', 'evidence_added',
      'recommendation_ready', 'execution_started', 'execution_log',
      'execution_completed', 'verification_result',
    ]

    eventTypes.forEach(type => {
      handlers[type] = (data) => {
        if (pausedRef.current) return
        const event = {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type,
          data,
          timestamp: new Date(),
        }
        setEvents(prev => [event, ...prev].slice(0, 500))
      }
    })

    const sse = createSSEConnection(
      handlers,
      (status) => {
        setConnected(status.connected)
        setReconnecting(status.retrying)
        if (status.initial !== undefined) setInitial(status.initial)
      }
    )

    return () => sse.close()
  }, [])

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = 0
    }
  }, [events, autoScroll])

  const filteredEvents = filter === 'all'
    ? events
    : events.filter(e => e.type === filter)

  const clearFeed = () => setEvents([])

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} initial={initial} />

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <Activity size={24} style={{ color: '#818cf8' }} />
            Live Feed
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && !paused && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Real-time event stream from the AIREX pipeline.
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-lg" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            {events.length} events
          </span>
          <button
            onClick={() => setPaused(!paused)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{
              fontSize: 12, fontWeight: 600,
              background: paused ? 'rgba(251,191,36,0.1)' : 'rgba(52,211,153,0.1)',
              color: paused ? '#fbbf24' : '#34d399',
              border: `1px solid ${paused ? 'rgba(251,191,36,0.2)' : 'rgba(52,211,153,0.2)'}`,
            }}
          >
            {paused ? <Play size={13} /> : <Pause size={13} />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            onClick={clearFeed}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all"
            style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
          >
            <Trash2 size={13} />
            Clear
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-1.5">
        {[
          { key: 'all', label: 'All' },
          { key: 'incident_created', label: 'Incidents' },
          { key: 'state_changed', label: 'State Changes' },
          { key: 'evidence_added', label: 'Evidence' },
          { key: 'recommendation_ready', label: 'AI Recommendations' },
          { key: 'execution_started', label: 'Executions' },
          { key: 'verification_result', label: 'Verifications' },
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className="px-3 py-1 rounded-md transition-all"
            style={{
              fontSize: 11, fontWeight: 600,
              background: filter === f.key ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
              color: filter === f.key ? '#818cf8' : 'var(--text-muted)',
              border: `1px solid ${filter === f.key ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`,
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Event Feed */}
      <div
        ref={feedRef}
        className="glass rounded-xl overflow-hidden"
        style={{ maxHeight: 'calc(100vh - 340px)', overflowY: 'auto' }}
      >
        {filteredEvents.length === 0 ? (
          <div className="py-20 text-center">
            <Radio size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
            <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>
              {paused ? 'Feed paused. Click Resume to continue.' : 'Waiting for events...'}
            </p>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, opacity: 0.6 }}>
              Send a webhook to see events appear here in real-time.
            </p>
          </div>
        ) : (
          filteredEvents.map(event => (
            <EventRow key={event.id} event={event} />
          ))
        )}
      </div>
    </div>
  )
}


function EventRow({ event }) {
  const config = EVENT_COLORS[event.type] || EVENT_COLORS.execution_log
  const data = event.data || {}
  const time = event.timestamp.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  const ms = String(event.timestamp.getMilliseconds()).padStart(3, '0')
  const incidentId = data.incident_id || data.id || ''

  return (
    <div
      className="flex items-start gap-3 px-4 py-2.5 transition-colors"
      style={{ borderBottom: '1px solid var(--border)', background: config.bg }}
    >
      {/* Timestamp */}
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', flexShrink: 0, marginTop: 2, minWidth: 85 }}>
        {time}.{ms}
      </span>

      {/* Event Type Badge */}
      <span
        className="inline-flex items-center rounded px-1.5 py-0.5 flex-shrink-0"
        style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.05em', color: config.accent, background: `${config.accent}15`, border: `1px solid ${config.accent}25`, minWidth: 60, justifyContent: 'center' }}
      >
        {config.label}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <EventContent type={event.type} data={data} />
      </div>

      {/* Link to incident */}
      {incidentId && (
        <Link to={`/incidents/${incidentId}`} className="flex-shrink-0" style={{ color: '#818cf8' }}>
          <ChevronRight size={14} />
        </Link>
      )}
    </div>
  )
}


function EventContent({ type, data }) {
  const mono = { fontFamily: 'var(--font-mono)', fontSize: 11 }

  switch (type) {
    case 'incident_created':
      return (
        <div className="flex items-center gap-2 flex-wrap">
          <span style={{ ...mono, color: '#60a5fa' }}>{truncateId(data.incident_id || data.id || '')}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{data.title || 'New incident'}</span>
          {data.severity && <SeverityBadge severity={data.severity} />}
        </div>
      )

    case 'state_changed':
      return (
        <div className="flex items-center gap-2 flex-wrap">
          <span style={{ ...mono, color: '#818cf8' }}>{truncateId(data.incident_id || '')}</span>
          <StateBadge state={data.from_state || data.old_state || '?'} />
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>-&gt;</span>
          <StateBadge state={data.new_state || data.to_state || '?'} />
          {data.reason && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>{data.reason.slice(0, 60)}</span>}
        </div>
      )

    case 'evidence_added':
      return (
        <div className="flex items-center gap-2">
          <span style={{ ...mono, color: '#34d399' }}>{truncateId(data.incident_id || '')}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>Evidence: {data.tool_name || 'unknown'}</span>
        </div>
      )

    case 'recommendation_ready':
      return (
        <div className="flex items-center gap-2 flex-wrap">
          <span style={{ ...mono, color: '#fbbf24' }}>{truncateId(data.incident_id || '')}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>
            AI recommends: <strong>{data.recommendation?.proposed_action || '?'}</strong>
          </span>
          {data.recommendation?.confidence && (
            <span style={{ ...mono, color: '#a78bfa' }}>({(data.recommendation.confidence * 100).toFixed(0)}%)</span>
          )}
        </div>
      )

    case 'execution_started':
      return (
        <div className="flex items-center gap-2">
          <span style={{ ...mono, color: '#38bdf8' }}>{truncateId(data.incident_id || '')}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>Executing: {data.action_type || '?'}</span>
        </div>
      )

    case 'execution_log':
      return (
        <span style={{ ...mono, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
          {typeof data === 'string' ? data : (data.message || data.line || JSON.stringify(data))}
        </span>
      )

    case 'execution_completed':
      return (
        <div className="flex items-center gap-2">
          <span style={{ ...mono, color: '#22d3ee' }}>{truncateId(data.incident_id || '')}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>
            {data.action_type || 'Action'}: <strong>{data.status || '?'}</strong>
          </span>
          {data.duration && <span style={{ ...mono, color: 'var(--text-muted)' }}>({data.duration.toFixed(1)}s)</span>}
        </div>
      )

    case 'verification_result':
      return (
        <div className="flex items-center gap-2">
          <span style={{ ...mono, color: '#34d399' }}>{truncateId(data.incident_id || '')}</span>
          <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>
            Verification: <strong style={{ color: data.result === 'RESOLVED' ? '#34d399' : '#fb7185' }}>{data.result || '?'}</strong>
          </span>
        </div>
      )

    default:
      return <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{JSON.stringify(data).slice(0, 100)}</span>
  }
}
