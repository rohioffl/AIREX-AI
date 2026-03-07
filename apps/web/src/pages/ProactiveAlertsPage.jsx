import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Radar, Bell, ShieldAlert, AlertOctagon, Radio,
  RefreshCw, Download, Filter, ArrowUpDown,
  ChevronLeft, ChevronRight, X, Activity
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import ConnectionBanner from '../components/common/ConnectionBanner'
import AlertRow from '../components/alert/AlertRow'

const ACTION_STATES = ['RECOMMENDATION_READY', 'AWAITING_APPROVAL']
const INVESTIGATING_STATES = ['RECEIVED', 'INVESTIGATING']
const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

const ALERT_FILTERS = [
  { key: 'all', label: 'All Proactive', icon: Bell },
  { key: 'critical', label: 'Critical', icon: AlertOctagon },
  { key: 'degraded', label: 'Degraded', icon: Activity },
  { key: 'investigating', label: 'Investigating', icon: Radio },
]

const SORT_OPTIONS = [
  { key: 'created_desc', label: 'Newest First', value: (a, b) => new Date(b.created_at) - new Date(a.created_at) },
  { key: 'created_asc', label: 'Oldest First', value: (a, b) => new Date(a.created_at) - new Date(b.created_at) },
  { key: 'severity', label: 'Severity', value: (a, b) => (SEVERITY_ORDER[a.severity] || 99) - (SEVERITY_ORDER[b.severity] || 99) },
  { key: 'updated_desc', label: 'Recently Updated', value: (a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at) },
]

export default function ProactiveAlertsPage() {
  const { incidents, loading, error, connected, reconnecting, reload } = useIncidents({
    alertType: 'healthcheck',
  })

  const [alertFilter, setAlertFilter] = useState('all')
  const [sortBy, setSortBy] = useState('created_desc')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    await reload()
    setTimeout(() => setRefreshing(false), 500)
  }

  const proactiveIncidents = useMemo(() => {
    return incidents.filter(i => i.alert_type === 'healthcheck' && i.state !== 'REJECTED')
  }, [incidents])

  const counts = useMemo(() => {
    const list = proactiveIncidents
    return {
      all: list.length,
      critical: list.filter(i => i.severity === 'CRITICAL').length,
      degraded: list.filter(i => i.severity === 'MEDIUM' || i.severity === 'LOW').length,
      investigating: list.filter(i => INVESTIGATING_STATES.includes(i.state)).length,
    }
  }, [proactiveIncidents])

  const visibleAlerts = useMemo(() => {
    let list = [...proactiveIncidents]

    switch (alertFilter) {
      case 'critical':
        list = list.filter(i => i.severity === 'CRITICAL')
        break
      case 'degraded':
        list = list.filter(i => i.severity === 'MEDIUM' || i.severity === 'LOW')
        break
      case 'investigating':
        list = list.filter(i => INVESTIGATING_STATES.includes(i.state))
        break
    }

    const sortFn = SORT_OPTIONS.find(o => o.key === sortBy)?.value || SORT_OPTIONS[0].value
    const sorted = list.sort(sortFn)

    const start = (page - 1) * pageSize
    return sorted.slice(start, start + pageSize)
  }, [proactiveIncidents, alertFilter, sortBy, page, pageSize])

  const totalFiltered = useMemo(() => {
    let list = proactiveIncidents
    switch (alertFilter) {
      case 'critical': return list.filter(i => i.severity === 'CRITICAL').length
      case 'degraded': return list.filter(i => i.severity === 'MEDIUM' || i.severity === 'LOW').length
      case 'investigating': return list.filter(i => INVESTIGATING_STATES.includes(i.state)).length
      default: return list.length
    }
  }, [proactiveIncidents, alertFilter])

  const totalPages = Math.ceil(totalFiltered / pageSize)

  const handleExport = () => {
    const csv = [
      ['ID', 'Title', 'Severity', 'State', 'Alert Type', 'Host', 'Created At', 'Updated At'].join(','),
      ...visibleAlerts.map(a => [
        a.id,
        `"${(a.title || '').replace(/"/g, '""')}"`,
        a.severity,
        a.state,
        a.alert_type || '',
        a.host_key || '',
        a.created_at,
        a.updated_at || a.created_at,
      ].join(','))
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `proactive-alerts-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} onRetry={reload} />

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <Radar size={24} style={{ color: '#22d3ee' }} />
            Proactive Alerts
            {counts.all > 0 && (
              <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full text-xs font-bold"
                style={{ background: counts.critical > 0 ? 'rgba(244,63,94,0.15)' : 'rgba(34,211,238,0.15)', color: counts.critical > 0 ? '#fb7185' : '#22d3ee' }}>
                {counts.all}
              </span>
            )}
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            {totalFiltered > 0
              ? `Showing ${visibleAlerts.length} of ${totalFiltered} proactive health check alerts`
              : 'Alerts auto-created by scheduled health checks when monitors report degraded or down status.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/health-checks"
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all"
            style={{
              background: 'rgba(34,211,238,0.08)',
              border: '1px solid rgba(34,211,238,0.2)',
              color: '#22d3ee',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Activity size={14} />
            Health Dashboard
          </Link>
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all disabled:opacity-50"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={handleExport}
            disabled={visibleAlerts.length === 0}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all disabled:opacity-50"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Download size={14} />
            Export
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {ALERT_FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => { setAlertFilter(f.key); setPage(1) }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{
              background: alertFilter === f.key ? 'rgba(34,211,238,0.1)' : 'var(--bg-elevated)',
              color: alertFilter === f.key ? '#22d3ee' : 'var(--text-secondary)',
              border: `1px solid ${alertFilter === f.key ? 'rgba(34,211,238,0.3)' : 'var(--border)'}`,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <f.icon size={14} />
            {f.label}
            <span className="ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-bold"
              style={{
                background: alertFilter === f.key ? 'rgba(34,211,238,0.2)' : 'var(--bg-input)',
                color: alertFilter === f.key ? '#67e8f9' : 'var(--text-muted)',
              }}>
              {counts[f.key]}
            </span>
          </button>
        ))}

        {/* Sort */}
        <div className="relative ml-auto">
          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(1) }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all appearance-none cursor-pointer"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 13,
              fontWeight: 600,
              paddingRight: 32,
            }}
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.key} value={opt.key}>{opt.label}</option>
            ))}
          </select>
          <ArrowUpDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-muted)' }} />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <div key={i} className="glass rounded-xl h-20 skeleton" />)}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid #f43f5e', background: 'rgba(244,63,94,0.03)', fontSize: 14, color: '#fb7185' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {/* Alert List */}
      {!loading && !error && (
        visibleAlerts.length === 0 ? (
          <div className="glass rounded-xl py-20 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full mb-4 hover-lift" style={{ background: 'rgba(34,211,238,0.1)', color: '#22d3ee' }}>
              <ShieldAlert size={24} />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>No proactive alerts</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>All monitored infrastructure is healthy. Health checks run every 5 minutes.</p>
          </div>
        ) : (
          <>
            <div className="space-y-1.5" style={{ width: '100%', maxWidth: '100%' }}>
              {visibleAlerts.map(alert => (
                <AlertRow key={alert.id} alert={alert} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4">
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Page {page} of {totalPages} ({totalFiltered} total)
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="flex items-center gap-1 px-3 py-2 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      background: page === 1 ? 'var(--bg-input)' : 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      color: page === 1 ? 'var(--text-muted)' : 'var(--text-secondary)',
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    <ChevronLeft size={14} />
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="flex items-center gap-1 px-3 py-2 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      background: page === totalPages ? 'var(--bg-input)' : 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      color: page === totalPages ? 'var(--text-muted)' : 'var(--text-secondary)',
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    Next
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </>
        )
      )}
    </div>
  )
}
