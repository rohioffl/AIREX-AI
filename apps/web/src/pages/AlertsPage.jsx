import { useMemo, useState, useEffect, useRef } from 'react'
import { useLocation, Link, useNavigate } from 'react-router-dom'
import { useWorkspacePath } from '../hooks/useWorkspacePath'
import {
  AlertTriangle, Bell,
  ShieldAlert, AlertOctagon, Radio, Zap, Server, Plus,
  RefreshCw, Download, Filter, ChevronLeft, ChevronRight,
  X, Search
} from 'lucide-react'
import CustomSelect from '../components/common/CustomSelect'
import useIncidents from '../hooks/useIncidents'
import ConnectionBanner from '../components/common/ConnectionBanner'
import AlertRow from '../components/alert/AlertRow'
import CreateIncidentModal from '../components/incident/CreateIncidentModal'
import { exportIncidents, bulkApprove, bulkReject } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../utils/errorHandler'

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
  const { activeOrganization } = useAuth()
  const { buildPath, isOrgScoped } = useWorkspacePath()
  const searchParams = new URLSearchParams(location.search)
  const urlSearch = searchParams.get('search') || ''
  const hostFilter = searchParams.get('host') || ''
  const organizationId = isOrgScoped ? activeOrganization?.id : null

  const { incidents, loading, error, connected, reconnecting, reload, setFilters } = useIncidents({ 
    search: urlSearch || null,
    host_key: hostFilter || null,
    organizationId,
  })
  const [alertFilter, setAlertFilter] = useState('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
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
  const [selectedIncidents, setSelectedIncidents] = useState(new Set())
  const [bulkActionLoading, setBulkActionLoading] = useState(false)
  const [bulkError, setBulkError] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const searchInputRef = useRef(null)
  const navigate = useNavigate()

  // Update filters when URL search or host changes
  useEffect(() => {
    setFilters(prev => ({
      ...prev,
      search: urlSearch || null,
      host_key: hostFilter || null,
      organizationId,
    }))
  }, [urlSearch, hostFilter, organizationId, setFilters])

  useEffect(() => {
    if (!organizationId) return
    setSelectedIncidents(new Set())
    setShowRejectInput(false)
    setRejectReason('')
    setBulkError(null)
  }, [organizationId])

  const toggleSelect = (id) => {
    setSelectedIncidents(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelectedIncidents(prev =>
      prev.size === visibleAlerts.length && visibleAlerts.length > 0
        ? new Set()
        : new Set(visibleAlerts.map(a => a.id))
    )
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await reload()
    setTimeout(() => setRefreshing(false), 500)
  }

  const handleExport = async () => {
    if (organizationId) {
      setExportError('Export is only available inside a single workspace.')
      return
    }
    setExportError(null)
    try {
      const filters = {}
      if (advancedFilters.alertType) filters.alert_type = advancedFilters.alertType
      if (advancedFilters.severity) filters.severity = advancedFilters.severity
      if (advancedFilters.dateFrom) filters.date_from = advancedFilters.dateFrom
      if (advancedFilters.dateTo) filters.date_to = advancedFilters.dateTo
      if (alertFilter !== 'all') {
        if (alertFilter === 'critical') filters.severity = 'CRITICAL'
        else if (alertFilter === 'action') filters.state = 'AWAITING_APPROVAL'
        else if (alertFilter === 'investigating') filters.state = 'INVESTIGATING'
      }

      const blob = await exportIncidents('csv', filters)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `incidents-${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(extractErrorMessage(err))
    }
  }

  const handleBulkApprove = async () => {
    setBulkActionLoading(true)
    setBulkError(null)
    try {
      const result = await bulkApprove(Array.from(selectedIncidents))
      if (result?.errors?.length > 0 && result.approved_count === 0) {
        setBulkError(`All failed: ${result.errors[0]}`)
      } else if (result?.errors?.length > 0) {
        setBulkError(`${result.approved_count} approved, ${result.errors.length} failed`)
      }
      setSelectedIncidents(new Set())
      await reload()
    } catch (err) {
      setBulkError(extractErrorMessage(err))
    } finally {
      setBulkActionLoading(false)
    }
  }

  const handleBulkReject = async () => {
    if (!rejectReason.trim()) {
      setBulkError('Rejection reason is required')
      return
    }
    setBulkActionLoading(true)
    setBulkError(null)
    try {
      const result = await bulkReject(Array.from(selectedIncidents), rejectReason.trim())
      if (result?.errors?.length > 0 && result.rejected_count === 0) {
        setBulkError(`All failed: ${result.errors[0]}`)
      } else if (result?.errors?.length > 0) {
        setBulkError(`${result.rejected_count} rejected, ${result.errors.length} failed`)
      }
      setSelectedIncidents(new Set())
      setShowRejectInput(false)
      setRejectReason('')
      if (result?.rejected_count > 0) {
        navigate(buildPath('rejected'))
      } else {
        await reload()
      }
    } catch (err) {
      setBulkError(extractErrorMessage(err))
    } finally {
      setBulkActionLoading(false)
    }
  }

   
  const visibleAlerts = useMemo(() => {
    let list = incidents
      .filter(i => i.state !== 'REJECTED' && i.alert_type !== 'healthcheck')
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
    let list = incidents.filter(i => i.state !== 'REJECTED' && i.alert_type !== 'healthcheck')
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
    const types = new Set(incidents.filter(i => i.state !== 'REJECTED' && i.alert_type !== 'healthcheck' && i.alert_type).map(i => i.alert_type))
    return Array.from(types).sort()
  }, [incidents])

  const counts = useMemo(() => {
    let list = incidents.filter(i => i.state !== 'REJECTED' && i.alert_type !== 'healthcheck')
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
        <div className="glass rounded-xl p-4 flex items-center justify-between gap-3" style={{ borderLeft: '3px solid rgba(99,102,241,0.4)' }}>
          <div className="flex items-center gap-2">
            <Server size={14} style={{ color: 'var(--neon-indigo)' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Showing alerts for server: <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{hostFilter}</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/alerts"
              className="text-sm transition-colors"
              style={{ color: 'var(--neon-indigo)', fontWeight: 500 }}
            >
              Clear filter
            </Link>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-3 py-1.5 rounded-lg flex items-center gap-2 transition-colors"
              style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)', color: 'var(--neon-green)', fontSize: 13, fontWeight: 600 }}
            >
              <Plus size={14} />
              Create Incident
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <AlertTriangle size={24} style={{ color: 'var(--brand-orange)' }} />
            {organizationId ? 'Organization Alerts' : 'Active Alerts'}
            {counts.all > 0 && (
              <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full text-xs font-bold"
                style={{ background: counts.critical > 0 ? 'rgba(244,63,94,0.15)' : 'rgba(251,146,60,0.15)', color: counts.critical > 0 ? 'var(--color-accent-red)' : 'var(--brand-orange)' }}>
                {counts.all}
              </span>
            )}
            <span className="relative w-2 h-2 rounded-full" style={{ background: connected ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}>
              {connected && <span className="absolute inset-0 rounded-full animate-ping" style={{ background: 'var(--color-accent-green)', opacity: 0.3 }} />}
            </span>
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            {totalFiltered > 0
              ? `Showing ${visibleAlerts.length} of ${totalFiltered} alerts`
              : (
                  organizationId
                    ? 'Alerts across all workspaces in this organization.'
                    : 'Incidents requiring attention, sorted by severity.'
                )}
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
            disabled={visibleAlerts.length === 0 || Boolean(organizationId)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all disabled:opacity-50"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 13,
              fontWeight: 600,
            }}
            title={organizationId ? 'Switch into a workspace to export alerts' : 'Export to CSV'}
          >
            <Download size={14} />
            Export
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="glass rounded-xl p-3">
        <div className="relative flex items-center">
          <div className="absolute left-3" style={{ color: 'var(--text-muted)' }}>
            <Search size={16} />
          </div>
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search incidents... (Press / to focus)"
            value={urlSearch}
            onChange={(e) => {
              const newSearch = e.target.value
              const newParams = new URLSearchParams(location.search)
              if (newSearch) {
                newParams.set('search', newSearch)
              } else {
                newParams.delete('search')
              }
              navigate(`${buildPath('alerts')}?${newParams.toString()}`, { replace: true })
            }}
            className="w-full pl-10 pr-3 py-2 rounded-lg outline-none transition-all"
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
              fontSize: 13,
            }}
          />
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
                color: alertFilter === f.key ? 'var(--neon-indigo)' : 'var(--text-secondary)',
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
                  color: alertFilter === f.key ? 'var(--neon-indigo)' : 'var(--text-muted)',
                }}>
                {counts[f.key]}
              </span>
            </button>
          ))}
          
          {/* Sort Dropdown */}
          <div className="ml-auto">
            <CustomSelect
              value={sortBy}
              onChange={(v) => { setSortBy(v || 'created_desc'); setPage(1) }}
              options={SORT_OPTIONS.map(o => ({ value: o.key, label: o.label }))}
              placeholder="Sort by…"
            />
          </div>

          {/* Advanced Filters Toggle */}
          <button
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg transition-all"
            style={{
              background: showAdvancedFilters ? 'rgba(99,102,241,0.1)' : 'var(--bg-elevated)',
              color: showAdvancedFilters ? 'var(--neon-indigo)' : 'var(--text-secondary)',
              border: `1px solid ${showAdvancedFilters ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Filter size={14} />
            Filters
            {(advancedFilters.alertType || advancedFilters.severity || advancedFilters.dateFrom || advancedFilters.dateTo) && (
              <span className="w-2 h-2 rounded-full" style={{ background: 'var(--neon-indigo)' }} />
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
                <CustomSelect
                  value={advancedFilters.alertType}
                  onChange={(v) => { setAdvancedFilters({ ...advancedFilters, alertType: v }); setPage(1) }}
                  options={uniqueAlertTypes}
                  placeholder="All Types"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Severity</label>
                <CustomSelect
                  value={advancedFilters.severity}
                  onChange={(v) => { setAdvancedFilters({ ...advancedFilters, severity: v }); setPage(1) }}
                  options={[
                    { value: 'CRITICAL', label: 'Critical' },
                    { value: 'HIGH', label: 'High' },
                    { value: 'MEDIUM', label: 'Medium' },
                    { value: 'LOW', label: 'Low' },
                  ]}
                  placeholder="All Severities"
                  style={{ width: '100%' }}
                />
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
          {[...Array(4)].map((_, i) => <div key={i} className="glass rounded-xl h-20 skeleton" />)}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="glass rounded-xl p-4" style={{ borderLeft: '4px solid var(--color-accent-red)', background: 'var(--glow-rose-subtle)', fontSize: 14, color: 'var(--color-accent-red)' }}>
          <span style={{ fontWeight: 700, marginRight: 8 }}>Error:</span>{error}
        </div>
      )}

      {/* Export error */}
      {exportError && (
        <div className="rounded-lg px-4 py-2.5 flex items-center justify-between gap-3"
          style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)', fontSize: 13, color: 'var(--color-accent-red)' }}>
          <span><span style={{ fontWeight: 700 }}>Export failed:</span> {exportError}</span>
          <button onClick={() => setExportError(null)} style={{ opacity: 0.7, lineHeight: 1 }}><X size={14} /></button>
        </div>
      )}

      {/* Alert List */}
      {!loading && !error && (
        visibleAlerts.length === 0 ? (
          <div className="glass rounded-xl py-20 text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-full mb-4 hover-lift" style={{ background: 'rgba(52,211,153,0.1)', color: 'var(--neon-green)' }}>
              <ShieldAlert size={24} />
            </div>
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)' }}>All clear</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>No active alerts matching this filter.</p>
          </div>
        ) : (
          <>
            {/* Selection Toolbar */}
            <div
              className="rounded-xl px-4 py-2.5 flex items-center gap-3 transition-all"
              style={{
                background: selectedIncidents.size > 0 ? 'rgba(99,102,241,0.06)' : 'var(--bg-elevated)',
                border: selectedIncidents.size > 0 ? '1px solid rgba(99,102,241,0.3)' : '1px solid var(--border)',
              }}
            >
              {organizationId ? (
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Cross-workspace view enabled. Open an alert to switch into its workspace before taking action.
                </span>
              ) : (
                <>
                  {/* Select All checkbox */}
                  <label className="flex items-center gap-2 cursor-pointer select-none" style={{ flexShrink: 0 }}>
                    <input
                      type="checkbox"
                      checked={selectedIncidents.size === visibleAlerts.length && visibleAlerts.length > 0}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded cursor-pointer"
                      style={{ accentColor: 'var(--neon-indigo)' }}
                    />
                    <span style={{ fontSize: 12, fontWeight: 600, color: selectedIncidents.size > 0 ? 'var(--neon-indigo)' : 'var(--text-secondary)' }}>
                      {selectedIncidents.size > 0 ? `${selectedIncidents.size} selected` : 'Select all'}
                    </span>
                  </label>

                  {/* Bulk actions — only visible when something is selected */}
                  {selectedIncidents.size > 0 && (
                <>
                  <div style={{ width: 1, height: 18, background: 'var(--border)', flexShrink: 0 }} />
                  {/* Approve only for "Needs Action" mode where approval is meaningful */}
                  {alertFilter === 'action' && (
                    <button
                      onClick={handleBulkApprove}
                      disabled={bulkActionLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all disabled:opacity-50"
                      style={{
                        background: 'rgba(16,185,129,0.1)',
                        border: '1px solid rgba(16,185,129,0.25)',
                        color: 'var(--neon-green)',
                        fontSize: 12,
                        fontWeight: 700,
                      }}
                    >
                      <Zap size={12} />
                      Approve
                    </button>
                  )}
                  {!showRejectInput ? (
                    <button
                      onClick={() => { setShowRejectInput(true); setBulkError(null) }}
                      disabled={bulkActionLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all disabled:opacity-50"
                      style={{
                        background: 'rgba(248,113,113,0.08)',
                        border: '1px solid rgba(248,113,113,0.2)',
                        color: 'var(--color-accent-red)',
                        fontSize: 12,
                        fontWeight: 700,
                      }}
                    >
                      <X size={12} />
                      Reject
                    </button>
                  ) : (
                    <>
                      <div style={{ width: 1, height: 18, background: 'var(--border)', flexShrink: 0 }} />
                      <input
                        autoFocus
                        type="text"
                        placeholder="Reason for rejection…"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleBulkReject()
                          if (e.key === 'Escape') { setShowRejectInput(false); setRejectReason(''); setBulkError(null) }
                        }}
                        className="px-3 py-1.5 rounded-lg outline-none"
                        style={{
                          background: 'var(--bg-input)',
                          border: '1px solid rgba(248,113,113,0.4)',
                          color: 'var(--text-primary)',
                          fontSize: 12,
                          width: 220,
                          flexShrink: 0,
                        }}
                      />
                      <button
                        onClick={handleBulkReject}
                        disabled={bulkActionLoading || !rejectReason.trim()}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all disabled:opacity-50"
                        style={{
                          background: 'rgba(248,113,113,0.12)',
                          border: '1px solid rgba(248,113,113,0.3)',
                          color: 'var(--color-accent-red)',
                          fontSize: 12,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {bulkActionLoading ? '…' : 'Confirm'}
                      </button>
                      <button
                        onClick={() => { setShowRejectInput(false); setRejectReason(''); setBulkError(null) }}
                        className="flex items-center gap-1 px-2 py-1.5 rounded-lg transition-all"
                        style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, background: 'var(--bg-input)', border: '1px solid var(--border)', flexShrink: 0 }}
                      >
                        Cancel
                      </button>
                    </>
                  )}
                  {!showRejectInput && (
                    <button
                      onClick={() => { setSelectedIncidents(new Set()); setShowRejectInput(false); setRejectReason(''); setBulkError(null) }}
                      className="flex items-center gap-1 transition-all"
                      style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginLeft: 'auto' }}
                    >
                      Clear
                    </button>
                  )}
                  {/* Inline bulk error */}
                  {bulkError && (
                    <span style={{ fontSize: 11, color: 'var(--color-accent-red)', marginLeft: showRejectInput ? 0 : 4 }}>
                      {bulkError}
                    </span>
                  )}
                </>
                  )}
                </>
              )}
            </div>
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
                    selected={organizationId ? false : selectedIncidents.has(alert.id)}
                    onSelect={organizationId ? null : toggleSelect}
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
                            color: page === pageNum ? 'var(--neon-indigo)' : 'var(--text-secondary)',
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

      {showCreateModal && (
        <CreateIncidentModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false)
            reload()
          }}
        />
      )}
    </div>
  )
}
