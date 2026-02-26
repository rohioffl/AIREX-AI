import { useMemo, useState, useEffect } from 'react'
import { useLocation, Link } from 'react-router-dom'
import {
  AlertTriangle, Bell,
  ShieldAlert, AlertOctagon, Radio, Zap, Server,
  RefreshCw, Download, Filter, ArrowUpDown, ChevronLeft, ChevronRight,
  X, Calendar, Search
} from 'lucide-react'
import useIncidents from '../hooks/useIncidents'
import ConnectionBanner from '../components/common/ConnectionBanner'
import AlertRow from '../components/alert/AlertRow'

const ACTION_STATES = ['RECOMMENDATION_READY', 'AWAITING_APPROVAL']
const INVESTIGATING_STATES = ['RECEIVED', 'INVESTIGATING']

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

const ALERT_FILTERS = [
  { key: 'all', label: 'All Active', icon: Bell },
  { key: 'critical', label: 'Critical', icon: AlertOctagon },
  { key: 'action', label: 'Needs Action', icon: Zap },
  { key: 'investigating', label: 'Investigating', icon: Radio },
]

const SORT_OPTIONS = [
  { key: 'created_desc', label: 'Newest First', value: (a, b) => new Date(b.created_at) - new Date(a.created_at) },
  { key: 'created_asc', label: 'Oldest First', value: (a, b) => new Date(a.created_at) - new Date(b.created_at) },
  { key: 'severity', label: 'Severity', value: (a, b) => (SEVERITY_ORDER[a.severity] || 99) - (SEVERITY_ORDER[b.severity] || 99) },
  { key: 'updated_desc', label: 'Recently Updated', value: (a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at) },
]

export default function AlertsPage() {
  const location = useLocation()
  const searchParams = new URLSearchParams(location.search)
  const urlSearch = searchParams.get('search') || ''
  const hostFilter = searchParams.get('host') || ''

  const { incidents, loading, error, connected, reconnecting, reload, setFilters } = useIncidents({ 
    search: urlSearch || null,
    host_key: hostFilter || null
  })
  const [alertFilter, setAlertFilter] = useState('all')
  const [sortBy, setSortBy] = useState('created_desc')
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
  const [advancedFilters, setAdvancedFilters] = useState({
    alertType: '',
    severity: '',
    dateFrom: '',
    dateTo: '',
  })
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [refreshing, setRefreshing] = useState(false)

  // Update filters when URL search or host changes
  useEffect(() => {
    setFilters(prev => ({
      ...prev,
      search: urlSearch || null,
      host_key: hostFilter || null
    }))
  }, [urlSearch, hostFilter, setFilters])

  const handleRefresh = async () => {
    setRefreshing(true)
    await reload()
    setTimeout(() => setRefreshing(false), 500)
  }

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
    a.download = `alerts-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // eslint-disable-next-line react-hooks/preserve-manual-memoization -- complex filter/sort/paginate logic, React Compiler cannot preserve
  const visibleAlerts = useMemo(() => {
    let list = incidents
      .filter(i => i.state !== 'REJECTED')
      .map(i => ({ ...i }))

    // Filter by host if host parameter is present
    if (hostFilter) {
      const decodedFilter = decodeURIComponent(hostFilter)
      list = list.filter(i => {
        // Try multiple ways to match host_key - check both direct field and meta fields
        const incidentHostKey = i.host_key || i.meta?._private_ip || i.meta?._instance_id || i.meta?.host || i.meta?._host || i.meta?.monitor_name
        
        if (!incidentHostKey) return false
        
        // Try exact match, decoded match, and case-insensitive match
        const hostKeyStr = String(incidentHostKey)
        const filterStr = String(hostFilter)
        const decodedFilterStr = String(decodedFilter)
        
        return hostKeyStr === filterStr || 
               hostKeyStr === decodedFilterStr ||
               hostKeyStr.toLowerCase() === filterStr.toLowerCase() ||
               hostKeyStr.toLowerCase() === decodedFilterStr.toLowerCase()
      })
    }

    // Apply advanced filters
    if (advancedFilters.alertType) {
      list = list.filter(i => i.alert_type === advancedFilters.alertType)
    }
    if (advancedFilters.severity) {
      list = list.filter(i => i.severity === advancedFilters.severity)
    }
    if (advancedFilters.dateFrom) {
      list = list.filter(i => new Date(i.created_at) >= new Date(advancedFilters.dateFrom))
    }
    if (advancedFilters.dateTo) {
      list = list.filter(i => new Date(i.created_at) <= new Date(advancedFilters.dateTo + 'T23:59:59'))
    }

    // Apply category filter
    switch (alertFilter) {
      case 'critical':
        list = list.filter(i => i.severity === 'CRITICAL')
        break
      case 'action':
        list = list.filter(i => ACTION_STATES.includes(i.state))
        break
      case 'investigating':
        list = list.filter(i => INVESTIGATING_STATES.includes(i.state))
        break
    }

    // Apply sorting
    const sortFn = SORT_OPTIONS.find(o => o.key === sortBy)?.value || SORT_OPTIONS[0].value
    const sorted = [...list].sort(sortFn)

    // Pagination
    const start = (page - 1) * pageSize
    const end = start + pageSize
    return sorted.slice(start, end)
  }, [incidents, alertFilter, hostFilter, advancedFilters, sortBy, page, pageSize])

  const totalFiltered = useMemo(() => {
    let list = incidents.filter(i => i.state !== 'REJECTED')
    if (hostFilter) {
      const decodedFilter = decodeURIComponent(hostFilter)
      list = list.filter(i => {
        const incidentHostKey = i.host_key || i.meta?._private_ip || i.meta?._instance_id || i.meta?.host || i.meta?._host || i.meta?.monitor_name
        
        if (!incidentHostKey) return false
        
        const hostKeyStr = String(incidentHostKey)
        const filterStr = String(hostFilter)
        const decodedFilterStr = String(decodedFilter)
        
        return hostKeyStr === filterStr || 
               hostKeyStr === decodedFilterStr ||
               hostKeyStr.toLowerCase() === filterStr.toLowerCase() ||
               hostKeyStr.toLowerCase() === decodedFilterStr.toLowerCase()
      })
    }
    if (advancedFilters.alertType) list = list.filter(i => i.alert_type === advancedFilters.alertType)
    if (advancedFilters.severity) list = list.filter(i => i.severity === advancedFilters.severity)
    if (advancedFilters.dateFrom) list = list.filter(i => new Date(i.created_at) >= new Date(advancedFilters.dateFrom))
    if (advancedFilters.dateTo) list = list.filter(i => new Date(i.created_at) <= new Date(advancedFilters.dateTo + 'T23:59:59'))
    switch (alertFilter) {
      case 'critical': return list.filter(i => i.severity === 'CRITICAL').length
      case 'action': return list.filter(i => ACTION_STATES.includes(i.state)).length
      case 'investigating': return list.filter(i => INVESTIGATING_STATES.includes(i.state)).length
      default: return list.length
    }
  }, [incidents, alertFilter, hostFilter, advancedFilters])

  const totalPages = Math.ceil(totalFiltered / pageSize)
  const uniqueAlertTypes = useMemo(() => {
    const types = new Set(incidents.filter(i => i.state !== 'REJECTED' && i.alert_type).map(i => i.alert_type))
    return Array.from(types).sort()
  }, [incidents])

  const counts = useMemo(() => {
    let list = incidents.filter(i => i.state !== 'REJECTED')
    // Apply host filter to counts if present - use same logic as visibleAlerts
    if (hostFilter) {
      const decodedFilter = decodeURIComponent(hostFilter)
      list = list.filter(i => {
        const incidentHostKey = i.host_key || i.meta?._private_ip || i.meta?._instance_id || i.meta?.host || i.meta?._host || i.meta?.monitor_name
        
        if (!incidentHostKey) return false
        
        const hostKeyStr = String(incidentHostKey)
        const filterStr = String(hostFilter)
        const decodedFilterStr = String(decodedFilter)
        
        return hostKeyStr === filterStr || 
               hostKeyStr === decodedFilterStr ||
               hostKeyStr.toLowerCase() === filterStr.toLowerCase() ||
               hostKeyStr.toLowerCase() === decodedFilterStr.toLowerCase()
      })
    }
    return {
      all: list.length,
      critical: list.filter(i => i.severity === 'CRITICAL').length,
      action: list.filter(i => ACTION_STATES.includes(i.state)).length,
      investigating: list.filter(i => INVESTIGATING_STATES.includes(i.state)).length,
    }
  }, [incidents, hostFilter])

  return (
    <div className="space-y-6 animate-fade-in">
      <ConnectionBanner connected={connected} reconnecting={reconnecting} onRetry={reload} />

      {hostFilter && (
        <div className="glass rounded-xl p-4 flex items-center justify-between" style={{ borderLeft: '3px solid rgba(99,102,241,0.4)' }}>
          <div className="flex items-center gap-2">
            <Server size={14} style={{ color: '#818cf8' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Showing alerts for server: <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{hostFilter}</span>
            </span>
          </div>
          <Link
            to="/alerts"
            className="text-sm transition-colors"
            style={{ color: '#818cf8', fontWeight: 500 }}
          >
            Clear filter
          </Link>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <AlertTriangle size={24} style={{ color: '#fb923c' }} />
            Active Alerts
            {counts.all > 0 && (
              <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full text-xs font-bold"
                style={{ background: counts.critical > 0 ? 'rgba(244,63,94,0.15)' : 'rgba(251,146,60,0.15)', color: counts.critical > 0 ? '#fb7185' : '#fb923c' }}>
                {counts.all}
              </span>
            )}
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? '#10b981' : '#f43f5e' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: '#10b981', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            {totalFiltered > 0 ? `Showing ${visibleAlerts.length} of ${totalFiltered} alerts` : 'Incidents requiring attention, sorted by severity.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
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
            title="Refresh alerts"
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
            title="Export to CSV"
          >
            <Download size={14} />
            Export
          </button>
        </div>
      </div>

      {/* Filter Tabs and Controls */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {ALERT_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => {
                setAlertFilter(f.key)
                setPage(1)
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
              style={{
                background: alertFilter === f.key ? 'rgba(99,102,241,0.1)' : 'var(--bg-elevated)',
                color: alertFilter === f.key ? '#818cf8' : 'var(--text-secondary)',
                border: `1px solid ${alertFilter === f.key ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              <f.icon size={14} />
              {f.label}
              <span className="ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-bold"
                style={{
                  background: alertFilter === f.key ? 'rgba(99,102,241,0.2)' : 'var(--bg-input)',
                  color: alertFilter === f.key ? '#a5b4fc' : 'var(--text-muted)',
                }}>
                {counts[f.key]}
              </span>
            </button>
          ))}
          
          {/* Sort Dropdown */}
          <div className="relative ml-auto">
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value)
                setPage(1)
              }}
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

          {/* Advanced Filters Toggle */}
          <button
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all"
            style={{
              background: showAdvancedFilters ? 'rgba(99,102,241,0.1)' : 'var(--bg-elevated)',
              color: showAdvancedFilters ? '#818cf8' : 'var(--text-secondary)',
              border: `1px solid ${showAdvancedFilters ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Filter size={14} />
            Filters
            {(advancedFilters.alertType || advancedFilters.severity || advancedFilters.dateFrom || advancedFilters.dateTo) && (
              <span className="w-2 h-2 rounded-full" style={{ background: '#818cf8' }} />
            )}
          </button>
        </div>

        {/* Advanced Filters Panel */}
        {showAdvancedFilters && (
          <div className="glass rounded-xl p-4 space-y-3" style={{ border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-2">
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-heading)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Advanced Filters</span>
              <button
                onClick={() => {
                  setAdvancedFilters({ alertType: '', severity: '', dateFrom: '', dateTo: '' })
                  setPage(1)
                }}
                className="flex items-center gap-1 px-2 py-1 rounded transition-colors"
                style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)' }}
              >
                <X size={12} />
                Clear
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Alert Type</label>
                <select
                  value={advancedFilters.alertType}
                  onChange={(e) => {
                    setAdvancedFilters({ ...advancedFilters, alertType: e.target.value })
                    setPage(1)
                  }}
                  className="w-full px-3 py-2 rounded-lg"
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  <option value="">All Types</option>
                  {uniqueAlertTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Severity</label>
                <select
                  value={advancedFilters.severity}
                  onChange={(e) => {
                    setAdvancedFilters({ ...advancedFilters, severity: e.target.value })
                    setPage(1)
                  }}
                  className="w-full px-3 py-2 rounded-lg"
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                >
                  <option value="">All Severities</option>
                  <option value="CRITICAL">Critical</option>
                  <option value="HIGH">High</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="LOW">Low</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>From Date</label>
                <input
                  type="date"
                  value={advancedFilters.dateFrom}
                  onChange={(e) => {
                    setAdvancedFilters({ ...advancedFilters, dateFrom: e.target.value })
                    setPage(1)
                  }}
                  className="w-full px-3 py-2 rounded-lg"
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>To Date</label>
                <input
                  type="date"
                  value={advancedFilters.dateTo}
                  onChange={(e) => {
                    setAdvancedFilters({ ...advancedFilters, dateTo: e.target.value })
                    setPage(1)
                  }}
                  className="w-full px-3 py-2 rounded-lg"
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <div key={i} className="glass rounded-xl h-20 shimmer" />)}
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
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full mb-4" style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399' }}>
              <ShieldAlert size={24} />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>All clear</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>No active alerts matching this filter.</p>
          </div>
        ) : (
          <>
            <div className="space-y-1.5" style={{ width: '100%', maxWidth: '100%' }}>
              {visibleAlerts.map(alert => {
                const manualReason = alert.meta?._manual_review_reason
                const manualReview = Boolean(alert.meta?._manual_review_required || manualReason)
                return (
                  <AlertRow
                    key={alert.id}
                    alert={alert}
                    manualReview={manualReview}
                    manualReason={manualReason}
                    manualAt={alert.meta?._manual_review_at}
                  />
                )
              })}
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
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum
                      if (totalPages <= 5) {
                        pageNum = i + 1
                      } else if (page <= 3) {
                        pageNum = i + 1
                      } else if (page >= totalPages - 2) {
                        pageNum = totalPages - 4 + i
                      } else {
                        pageNum = page - 2 + i
                      }
                      return (
                        <button
                          key={pageNum}
                          onClick={() => setPage(pageNum)}
                          className="w-8 h-8 rounded-lg transition-all"
                          style={{
                            background: page === pageNum ? 'rgba(99,102,241,0.1)' : 'var(--bg-elevated)',
                            border: `1px solid ${page === pageNum ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
                            color: page === pageNum ? '#818cf8' : 'var(--text-secondary)',
                            fontSize: 13,
                            fontWeight: 600,
                          }}
                        >
                          {pageNum}
                        </button>
                      )
                    })}
                  </div>
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
