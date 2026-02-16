import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, AlertOctagon, CheckCircle, Clock,
  LayoutGrid, List as ListIcon
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import IncidentCard from '../components/incident/IncidentCard'
import MetricCard from '../components/common/MetricCard'
import SystemGraph from '../components/common/SystemGraph'
import ConnectionBanner from '../components/common/ConnectionBanner'
import StateBadge from '../components/common/StateBadge'
import SeverityBadge from '../components/common/SeverityBadge'
import { formatTimestamp, truncateId } from '../utils/formatters'

const STATES = [
  'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY', 'AWAITING_APPROVAL',
  'EXECUTING', 'VERIFYING', 'RESOLVED', 'FAILED_ANALYSIS', 'FAILED_EXECUTION',
  'FAILED_VERIFICATION', 'ESCALATED',
]
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function IncidentList() {
  const { incidents, loading, error, connected, reconnecting, filters, setFilters } = useIncidents()
  const [view, setView] = useState('list')
  const [graphType, setGraphType] = useState('area')

  const stats = useMemo(() => ({
    total: incidents.length,
    active: incidents.filter(i => !['RESOLVED', 'ESCALATED'].includes(i.state)).length,
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
            Dashboard
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
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['ID', 'Severity', 'Title', 'State', 'Created'].map(h => (
                    <th key={h} className={`px-5 py-3 ${h === 'Created' ? 'text-right' : ''}`} style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {incidents.map(inc => (
                  <tr key={inc.id} className="group transition-colors" style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="px-5 py-3.5" style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                      <Link to={`/incidents/${inc.id}`} style={{ color: '#818cf8' }}>{truncateId(inc.id)}</Link>
                    </td>
                    <td className="px-5 py-3.5"><SeverityBadge severity={inc.severity} /></td>
                    <td className="px-5 py-3.5">
                      <Link to={`/incidents/${inc.id}`} className="block">
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{inc.title}</span>
                        <span className="block mt-0.5" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{inc.alert_type}</span>
                      </Link>
                    </td>
                    <td className="px-5 py-3.5"><StateBadge state={inc.state} /></td>
                    <td className="px-5 py-3.5 text-right" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{formatTimestamp(inc.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
