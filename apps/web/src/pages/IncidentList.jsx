import { useMemo, useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell,
  AlertOctagon,
  CheckCircle,
  Clock,
  LayoutGrid,
  List as ListIcon,
  Search,
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import IncidentCard from '../components/incident/IncidentCard'
import IncidentListRow from '../components/incident/IncidentListRow'
import MetricCard from '../components/common/MetricCard'
import SystemGraph from '../components/common/SystemGraph'
import ConnectionBanner from '../components/common/ConnectionBanner'
import CustomSelect from '../components/common/CustomSelect'

const STATES = [
  'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY', 'AWAITING_APPROVAL',
  'EXECUTING', 'VERIFYING', 'RESOLVED', 'FAILED_ANALYSIS', 'FAILED_EXECUTION',
  'FAILED_VERIFICATION', 'REJECTED',
]
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
const ALERT_TYPES = ['cpu_high', 'memory_high', 'disk_full', 'healthcheck', 'network_check']

export default function IncidentList({ initialFilters = {}, title = 'Dashboard' }) {
  const { incidents, loading, error, connected, reconnecting, filters, setFilters, loadMore, hasMore, total } = useIncidents(initialFilters)
  const [view, setView] = useState('list')
  const [graphType, setGraphType] = useState('area')
  const [searchInput, setSearchInput] = useState(filters.search || '')
  const [isSearchFocused, setIsSearchFocused] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters(f => {
        if (f.search === (searchInput || undefined) || f.search === searchInput) return f
        return { ...f, search: searchInput || undefined }
      })
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput, setFilters])

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
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: 'var(--color-accent-green)', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Real-time incident monitoring and autonomous resolution.
            {total !== undefined && total !== null && (
              <span className="ml-3 font-mono text-xs px-2 py-0.5 rounded-md" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                Showing {incidents.length} of {total}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
              { label: 'MTTR', value: '—', color: 'var(--color-accent-green)' }, // Will be populated from metrics API
              { label: 'Avg Investigation', value: '—', color: 'var(--neon-indigo)' },
              { label: 'AI Confidence', value: '—', color: 'var(--neon-purple)' },
              { label: 'Auto-resolved', value: `${stats.resolved}`, color: 'var(--neon-cyan)' },
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
                  color: graphType === t ? 'var(--neon-indigo)' : 'var(--text-muted)',
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
          <div className="relative flex items-center w-full md:w-48">
            <div className="absolute left-2.5" style={{ color: isSearchFocused ? 'var(--neon-indigo)' : 'var(--text-muted)' }}>
              <Search size={14} />
            </div>
            <input
              type="text"
              placeholder="Search..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setIsSearchFocused(false)}
              className={`w-full pl-8 pr-3 py-1.5 rounded-lg outline-none transition-all placeholder:opacity-50 ${isSearchFocused ? 'glow-indigo' : ''}`}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--text-secondary)',
                background: 'var(--bg-input)',
                border: isSearchFocused ? '1px solid rgba(99,102,241,0.5)' : '1px solid var(--border)',
              }}
            />
          </div>
          <CustomSelect value={filters.alertType || ''} onChange={(v) => setFilters(f => ({ ...f, alertType: v || null }))} options={ALERT_TYPES} placeholder="All Alert Types" />
          <CustomSelect value={filters.state || ''} onChange={(v) => setFilters(f => ({ ...f, state: v || null }))} options={STATES} placeholder="All States" />
          <CustomSelect value={filters.severity || ''} onChange={(v) => setFilters(f => ({ ...f, severity: v || null }))} options={SEVERITIES} placeholder="All Severities" />
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
          <div className="glass rounded-xl h-16 skeleton" />
          <div className="glass rounded-xl h-20 skeleton" />
          <div className="glass rounded-xl h-24 skeleton" />
          <div className="glass rounded-xl h-16 skeleton" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid var(--color-accent-red)', background: 'var(--glow-rose-subtle)', fontSize: 14, color: 'var(--color-accent-red)' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && (
        incidents.length === 0 ? (
          <div className="glass glass-cyan rounded-xl py-20 text-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-[rgba(34,211,238,0.05)] to-transparent pointer-events-none" />
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full mb-4 relative z-10" style={{ background: 'var(--bg-input)', color: 'var(--neon-cyan)', border: '1px solid rgba(34,211,238,0.2)', boxShadow: '0 0 15px rgba(34,211,238,0.1)' }}>
              <Bell size={20} />
            </div>
            <p className="relative z-10" style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No incidents match your criteria.</p>
          </div>
        ) : (
          <>
            {view === 'grid' ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <AnimatePresence mode="popLayout">
                  {incidents.map((inc, i) => (
                    <motion.div
                      key={inc.id}
                      layout
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ delay: Math.min(i * 0.04, 0.3), duration: 0.28, ease: 'easeOut' }}
                    >
                      <IncidentCard incident={inc} />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            ) : (
              <div className="space-y-3">
                <AnimatePresence mode="popLayout">
                  {incidents.map((inc, i) => (
                    <motion.div
                      key={inc.id}
                      layout
                      initial={{ opacity: 0, x: -16 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 16, scale: 0.98 }}
                      transition={{ delay: Math.min(i * 0.035, 0.25), duration: 0.25, ease: 'easeOut' }}
                    >
                      <IncidentListRow incident={inc} />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
            {hasMore && (
              <div className="flex justify-center pt-4">
                <button onClick={loadMore} className="px-6 py-2.5 rounded-xl font-semibold text-sm transition-all hover-lift" style={{ background: 'var(--glow-indigo)', color: 'var(--neon-indigo)', border: '1px solid rgba(99,102,241,0.2)' }}>
                  Load More Incidents
                </button>
              </div>
            )}
          </>
        )
      )}
    </div>
  )
}


