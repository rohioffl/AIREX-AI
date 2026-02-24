import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell,
  AlertOctagon,
  CheckCircle,
  Clock,
  Repeat,
  LayoutGrid,
  List as ListIcon,
  Activity,
  AlertTriangle,
  GaugeCircle,
  Radio,
  ArrowUpRight,
  ChevronRight,
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import IncidentCard from '../components/incident/IncidentCard'
import MetricCard from '../components/common/MetricCard'
import SystemGraph from '../components/common/SystemGraph'
import ConnectionBanner from '../components/common/ConnectionBanner'
import StateBadge from '../components/common/StateBadge'
import SeverityBadge from '../components/common/SeverityBadge'
import { formatTimestamp, truncateId, formatDuration } from '../utils/formatters'

const STATES = [
  'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY', 'AWAITING_APPROVAL',
  'EXECUTING', 'VERIFYING', 'RESOLVED', 'FAILED_ANALYSIS', 'FAILED_EXECUTION',
  'FAILED_VERIFICATION', 'REJECTED',
]
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function IncidentList({ initialFilters = {}, title = 'Dashboard' }) {
  const { incidents, loading, error, connected, reconnecting, filters, setFilters } = useIncidents(initialFilters)
  const [view, setView] = useState('list')
  const [graphType, setGraphType] = useState('area')

  const stats = useMemo(() => ({
    total: incidents.length,
    active: incidents.filter(i => !['RESOLVED', 'REJECTED'].includes(i.state)).length,
    critical: incidents.filter(i => i.severity === 'CRITICAL').length,
    resolved: incidents.filter(i => i.state === 'RESOLVED').length,
  }), [incidents])

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} />
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            {title}
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Real-time incident monitoring and autonomous resolution.
          </p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Total Alerts" value={String(stats.total)} trend="All time" trendType="neutral" icon={Bell} />
        <MetricCard title="Critical" value={String(stats.critical)} trend={stats.critical > 0 ? 'Needs attention' : 'All clear'} trendType={stats.critical > 0 ? 'negative' : 'positive'} isCritical={stats.critical > 0} icon={AlertOctagon} />
        <MetricCard title="Active" value={String(stats.active)} trend="Awaiting action" trendType="neutral" icon={Clock} />
        <MetricCard title="Resolved" value={String(stats.resolved)} trend="AI assisted" trendType="positive" icon={CheckCircle} />
      </div>

      {/* Graph Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SystemGraph incidents={incidents} type={graphType} />
        </div>
        <div className="glass p-5 flex flex-col gap-4">
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Quick Stats</span>
          <div className="flex-1 flex flex-col gap-3">
            {[
              { label: 'MTTR', value: '4m 23s', color: '#10b981' },
              { label: 'Avg Investigation', value: '45s', color: '#6366f1' },
              { label: 'AI Confidence', value: '87%', color: '#a855f7' },
              { label: 'Auto-resolved', value: `${stats.resolved}`, color: '#22d3ee' },
            ].map(s => (
              <div key={s.label} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.label}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: s.color }}>{s.value}</span>
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-auto">
            {['area', 'bar'].map(t => (
              <button
                key={t}
                onClick={() => setGraphType(t)}
                className="flex-1 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-all"
                style={{
                  background: graphType === t ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)',
                  color: graphType === t ? '#818cf8' : 'var(--text-muted)',
                  border: `1px solid ${graphType === t ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="glass rounded-xl p-3 flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <Select value={filters.state || ''} onChange={(v) => setFilters(f => ({ ...f, state: v || null }))} options={STATES} placeholder="All States" />
          <Select value={filters.severity || ''} onChange={(v) => setFilters(f => ({ ...f, severity: v || null }))} options={SEVERITIES} placeholder="All Severities" />
        </div>
        <div className="flex rounded-lg p-0.5" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
          {[
            { key: 'list', Icon: ListIcon },
            { key: 'grid', Icon: LayoutGrid },
          ].map(v => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all"
              style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                background: view === v.key ? 'var(--bg-elevated)' : 'transparent',
                color: view === v.key ? 'var(--text-heading)' : 'var(--text-muted)',
              }}
            >
              <v.Icon size={13} />
              {v.key}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <div key={i} className="glass rounded-xl h-16 shimmer" />)}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid #f43f5e', background: 'rgba(244,63,94,0.03)', fontSize: 14, color: '#fb7185' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && (
        incidents.length === 0 ? (
          <div className="glass rounded-xl py-20 text-center">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full mb-4" style={{ background: 'var(--bg-input)', color: 'var(--text-muted)' }}>
              <Bell size={20} />
            </div>
            <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>No incidents match your criteria.</p>
          </div>
        ) : view === 'grid' ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {incidents.map(inc => <IncidentCard key={inc.id} incident={inc} />)}
          </div>
        ) : (
          <div className="space-y-3">
            {incidents.map(inc => (
              <IncidentListRow key={inc.id} incident={inc} />
            ))}
          </div>
        )
      )}
    </div>
  )
}

function Select({ value, onChange, options, placeholder }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none pl-3 pr-7 py-1.5 rounded-lg outline-none transition-all"
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-secondary)',
          background: 'var(--bg-input)',
          border: '1px solid var(--border)',
        }}
      >
        <option value="">{placeholder}</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2" style={{ color: 'var(--text-muted)' }}>
        <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" /></svg>
      </div>
    </div>
  )
}

const SEVERITY_SHADES = {
  CRITICAL: '#f43f5e',
  HIGH: '#fb923c',
  MEDIUM: '#22d3ee',
  LOW: '#10b981',
}

function IncidentListRow({ incident }) {
  const meta = incident.meta || {}
  const alertCount = meta._alert_count != null ? Number(meta._alert_count) : 1
  const durationSec = meta._alert_duration_seconds != null ? Number(meta._alert_duration_seconds) : null
  const unstable = Boolean(meta._unstable)
  const cloud = meta._cloud || meta.cloud
  const tenant = meta._tenant_name || meta.tenant
  const manualReason = typeof meta._manual_review_reason === 'string' ? meta._manual_review_reason.trim() : ''
  const manualReview = Boolean(meta._manual_review_required || manualReason)
  const manualAt = meta._manual_review_at ? formatTimestamp(String(meta._manual_review_at)) : null
  const accent = manualReview ? '#f87171' : (SEVERITY_SHADES[incident.severity] || '#6366f1')

  return (
    <Link
      to={`/incidents/${incident.id}`}
      className="block rounded-2xl relative overflow-hidden"
      style={{ border: '1px solid rgba(255,255,255,0.04)', background: 'var(--bg-card)' }}
    >
      <div
        className="absolute inset-y-3 left-3 w-[3px] rounded-full"
        style={{ background: accent, opacity: 0.85 }}
      />
      <div className="pl-6 pr-4 py-3 flex items-center gap-4">
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px]" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            <span>{truncateId(incident.id)}</span>
            <span>• {formatTimestamp(incident.created_at)}</span>
            {tenant && <span>• tenant {tenant}</span>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={incident.severity} />
            <StateBadge state={incident.state} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{incident.alert_type}</span>
            {cloud && (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <Radio size={11} /> {cloud}
              </span>
            )}
            {manualReview && (
              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5" style={{ fontSize: 11, color: '#f87171', background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.25)' }}>
                Manual Review
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2" style={{ color: 'var(--text-heading)', fontWeight: 600, fontSize: 15 }}>
            {incident.title}
            <ArrowUpRight size={16} />
          </div>
          <div className="flex flex-wrap gap-2" style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span className="rounded-md px-2 py-0.5" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
              <Repeat size={10} /> {alertCount}x
            </span>
            {durationSec && (
              <span className="rounded-md px-2 py-0.5" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                <Clock size={10} /> {formatDuration(durationSec)}
              </span>
            )}
            {unstable && (
              <span className="rounded-md px-2 py-0.5" style={{ background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.25)', color: '#fbbf24' }}>
                <AlertTriangle size={10} /> flapping
              </span>
            )}
            {meta.recommendation?.confidence && (
              <span className="rounded-md px-2 py-0.5" style={{ background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.2)', color: '#38bdf8' }}>
                <GaugeCircle size={10} /> {Math.round(meta.recommendation.confidence * 100)}% AI
              </span>
            )}
            {meta.recommendation?.proposed_action && (
              <span className="rounded-md px-2 py-0.5" style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: '#fb7185' }}>
                <Activity size={10} /> {meta.recommendation.proposed_action}
              </span>
            )}
          </div>
          {manualReason && (
            <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              <span style={{ color: '#f87171', fontWeight: 600 }}>Operator note:</span> {manualReason}
              {manualAt && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>({manualAt})</span>}
            </p>
          )}
        </div>
        <ChevronRight size={18} style={{ color: 'var(--text-muted)' }} />
      </div>
    </Link>
  )
}
