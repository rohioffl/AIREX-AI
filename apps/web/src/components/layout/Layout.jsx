import { useState, useEffect, useRef, forwardRef } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, AlertTriangle, Settings,
  Sun, Moon, Bell, BellRing, PanelLeftClose, PanelLeft, Search, LogOut,
  X, ChevronRight, Clock, Zap, Ban, HeartPulse, TrendingUp, BookOpen,
  Terminal, Layers, BarChart3, ShieldCheck, ClipboardList, Building2, Check
} from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import { useAuth } from '../../context/AuthContext'
import { fetchIncidents, fetchUserAccessibleTenants } from '../../services/api'
import { createSSEConnection } from '../../services/sse'
import {
  canAccessRoute,
  normalizeRole,
} from '../../utils/accessControl'
import ToastContainer from '../common/ToastContainer'
import LeadApprovalPanel from './LeadApprovalPanel'

const ACTIVE_STATES = [
  'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY',
  'AWAITING_APPROVAL', 'EXECUTING', 'VERIFYING',
]

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Alerts', path: '/alerts', icon: AlertTriangle, showBadge: true, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Analytics', path: '/analytics', icon: TrendingUp, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Knowledge Base', path: '/knowledge-base', icon: BookOpen, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Rejected', path: '/rejected', icon: Ban, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Live Monitoring', path: '/health-checks', icon: HeartPulse, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Runbooks', path: '/runbooks', icon: Terminal, roles: ['admin', 'operator'] },
  { label: 'Proactive', path: '/patterns', icon: Layers, roles: ['admin', 'operator', 'viewer'] },
  { label: 'Reports', path: '/reports', icon: BarChart3, roles: ['admin', 'operator'] },
  { label: 'Settings', path: '/settings', icon: Settings, roles: ['admin', 'operator'] },
  { label: 'Org Settings', path: '/org-settings', icon: Building2, roles: ['admin'] },
  { label: 'Platform Admin', path: '/admin', icon: ShieldCheck, access: 'platform_admin' },
  { label: 'Org Admin', path: '/org-admin', icon: Building2, access: 'organizations_admin' },
  { label: 'Tenant Workspaces', path: '/admin/workspaces', icon: Layers, access: 'tenant_admin' },
  { label: 'Integrations', path: '/admin/integrations', icon: Zap, access: 'tenant_admin' },
]

const ROUTE_TITLES = {
  '/dashboard':              { label: 'Dashboard',        parent: null },
  '/alerts':                 { label: 'Active Alerts',    parent: null },
  '/analytics':              { label: 'Analytics',        parent: null },
  '/knowledge-base':         { label: 'Knowledge Base',   parent: null },
  '/rejected':               { label: 'Rejected',         parent: null },
  '/live':                   { label: 'Live Feed',        parent: null },
  '/health-checks':          { label: 'Live Monitoring',  parent: null },
  '/health-checks/site24x7': { label: 'Site24x7',         parent: 'Live Monitoring' },
  '/runbooks':               { label: 'Runbooks',         parent: null },
  '/patterns':               { label: 'Proactive',        parent: null },
  '/reports':                { label: 'Reports',          parent: null },
  '/settings':               { label: 'Settings',         parent: null },
  '/org-settings':           { label: 'Org Settings',     parent: null },
  '/org-admin':              { label: 'Org Admin',        parent: null },
  '/admin':                  { label: 'Platform Admin',   parent: null },
  '/admin/organizations':    { label: 'Organizations',    parent: null },
  '/admin/workspaces':       { label: 'Tenant Workspaces', parent: null },
  '/admin/integrations':     { label: 'Integrations',     parent: null },
  '/profile':               { label: 'Profile',           parent: 'Account' },
}

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { isDark, toggle } = useTheme()
  const {
    user,
    logout,
    tenants,
    activeTenant,
    activeOrganization,
    switchTenant,
    organizations,
    organizationMemberships,
    tenantMemberships,
  } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeAlertIds, setActiveAlertIds] = useState(new Set())
  const [activeCriticalIds, setActiveCriticalIds] = useState(new Set())
  const alertCount = activeAlertIds.size
  const criticalCount = activeCriticalIds.size
  const [notifications, setNotifications] = useState([])
  const [showNotifications, setShowNotifications] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showLeadApproval, setShowLeadApproval] = useState(false)
  const bellRef = useRef(null)
  const dropdownRef = useRef(null)

  // Sync search query from URL into local state during render
  // (React-recommended pattern for deriving state from external values)
  const urlSearchParam = new URLSearchParams(location.search).get('search') || ''
  if (searchQuery !== urlSearchParam) {
    setSearchQuery(urlSearchParam)
  }

  const isActive = (path) => location.pathname.startsWith(path)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  // Persist read notification IDs across page refreshes
  const STORAGE_KEY = 'airex-read-notification-ids'
  function getReadIds() {
    try { return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')) } catch { return new Set() }
  }
  function saveReadIds(ids) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids])) } catch { /* ignore */ }
  }

  // Load initial alert counts
  useEffect(() => {
    let cancelled = false
    async function loadAlerts() {
      try {
        const data = await fetchIncidents({ limit: 200 })
        if (cancelled) return
        const readIds = getReadIds()
        const items = data.items || []
        const active = items.filter(i => ACTIVE_STATES.includes(i.state))
        const nonHealthCheck = active.filter(i => i.alert_type !== 'healthcheck')
        setActiveAlertIds(new Set(nonHealthCheck.map(i => i.id)))
        setActiveCriticalIds(new Set(nonHealthCheck.filter(i => i.severity === 'CRITICAL').map(i => i.id)))
        setNotifications(active.slice(0, 10).map(i => ({
          id: i.id,
          title: i.title || 'Alert',
          severity: i.severity || 'MEDIUM',
          state: i.state || 'RECEIVED',
          alert_type: i.alert_type || 'unknown',
          created_at: i.created_at || '',
          read: readIds.has(i.id),
        })))
      } catch (err) {
        console.warn('Failed to load alert counts:', err)
      }
    }
    loadAlerts()
    return () => { cancelled = true }
  }, [])

  // SSE for real-time alert count updates
  useEffect(() => {
    let sse = null
    try {
      sse = createSSEConnection(
        {
          incident_created(data) {
            if (data.alert_type !== 'healthcheck') {
              setActiveAlertIds(prev => new Set(prev).add(data.incident_id || data.id))
              if (data.severity === 'CRITICAL') {
                setActiveCriticalIds(prev => new Set(prev).add(data.incident_id || data.id))
              }
            }
            setNotifications(prev => [{
              id: data.incident_id || data.id || '',
              title: data.title || 'New Alert',
              severity: data.severity || 'MEDIUM',
              state: data.state || 'RECEIVED',
              alert_type: data.alert_type || 'unknown',
              created_at: new Date().toISOString(),
              read: false,
            }, ...prev].slice(0, 20))
          },
          state_changed(data) {
            const resolvedStates = ['RESOLVED', 'FAILED_ANALYSIS', 'FAILED_EXECUTION', 'REJECTED']
            if (resolvedStates.includes(data.new_state)) {
              setActiveAlertIds(prev => {
                const next = new Set(prev)
                next.delete(data.incident_id)
                return next
              })
              setActiveCriticalIds(prev => {
                const next = new Set(prev)
                next.delete(data.incident_id)
                return next
              })
            }
            setNotifications(prev =>
              prev.map(n => n.id === data.incident_id ? { ...n, state: data.new_state } : n)
            )
          },
        },
        () => { }
      )
    } catch (err) {
      console.warn('SSE connection failed in Layout:', err)
    }
    return () => { if (sse) sse.close() }
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        bellRef.current && !bellRef.current.contains(e.target)
      ) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const unreadCount = notifications.filter(n => !n.read && ACTIVE_STATES.includes(n.state)).length
  const markAllRead = () => {
    setNotifications(prev => {
      const updated = prev.map(n => ({ ...n, read: true }))
      saveReadIds(new Set(updated.map(n => n.id)))
      return updated
    })
  }

  const initials = user?.displayName
    ? user.displayName.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : user?.email
      ? user.email.substring(0, 2).toUpperCase()
      : 'OP'

  const displayName = user?.displayName
    || (user?.email
      ? user.email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
      : 'Operator')
  const accessContext = {
    user,
    activeOrganization,
    activeTenantId: activeTenant?.id,
    organizationMemberships,
    tenantMemberships,
  }

  return (
    <div className="min-h-screen overflow-x-hidden" style={{ background: 'var(--bg-body)', color: 'var(--text-primary)' }}>
      {/* Sidebar */}
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'open' : ''}`}>
        {/* AIREX Brand */}
        <div className="sidebar-brand" style={{ padding: collapsed ? '20px 0' : '20px 20px', justifyContent: collapsed ? 'center' : 'flex-start' }}>
          <div className="sidebar-brand-logo">A</div>
          {!collapsed && (
            <div className="sidebar-brand-text">
              <span className="sidebar-brand-name">AIREX</span>
              <span className="sidebar-brand-sub">Cloud SRE Platform</span>
            </div>
          )}
        </div>

        {/* Workspace / Org Switcher */}
        <SidebarWorkspaceSwitcher 
          organizations={organizations}
          activeOrganization={activeOrganization}
          tenants={tenants}
          activeTenant={activeTenant}
          switchTenant={switchTenant}
          currentUserId={user?.userId || user?.user_id || null}
          navigate={navigate}
          collapsed={collapsed}
        />

        {/* Nav */}
        <nav className="sidebar-nav">
          <div className="sidebar-section-label">
            <span className="sidebar-label">Navigation</span>
          </div>
          {NAV_ITEMS.filter(item => {
            if (item.access) {
              return canAccessRoute(accessContext, item.access)
            }
            // Filter by role if roles are specified
            if (item.roles && user) {
              const userRole = normalizeRole(user.role || 'operator')
              return item.roles.map(r => r.toLowerCase()).includes(userRole)
            }
            // Show all items if no role filter or no user (dev mode)
            return true
          }).map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`sidebar-nav-item ${isActive(item.path) ? 'active' : ''}`}
              onClick={() => setMobileOpen(false)}
            >
              <div className="relative">
                <item.icon size={18} />
                {item.showBadge && alertCount > 0 && (
                  <span
                    className="absolute -top-1.5 -right-1.5 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[9px] font-bold"
                    style={{
                      background: criticalCount > 0 ? 'var(--color-accent-red)' : 'var(--brand-orange)',
                      color: '#fff',
                      lineHeight: 1,
                    }}
                  >
                    {alertCount > 99 ? '99+' : alertCount}
                  </span>
                )}
              </div>
              <span className="sidebar-label">{item.label}</span>
            </Link>
          ))}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <Link
              to="/profile"
              className="flex items-center gap-2 flex-1 min-w-0"
              style={{ textDecoration: 'none', color: 'inherit' }}
              onClick={() => setMobileOpen(false)}
            >
              <div className="sidebar-avatar">{initials}</div>
              <div className="sidebar-footer-text">
                <span className="sidebar-user-name">{displayName}</span>
                {normalizeRole(user?.role) === 'platform_admin' && (
                  <span style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--neon-indigo)', borderRadius: 999, padding: '1px 7px', fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', display: 'inline-block', marginTop: 1 }}>
                    PLATFORM ADMIN
                  </span>
                )}
                <span className="sidebar-user-role" style={{ opacity: 0.65 }}>{user?.email || 'dev mode'}</span>
              </div>
            </Link>
            {user && (
              <button
                onClick={handleLogout}
                title="Sign out"
                className="sidebar-label"
                style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4, flexShrink: 0 }}
              >
                <LogOut size={14} />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex flex-col min-h-screen transition-[padding] duration-300" style={{ paddingLeft: collapsed ? 64 : 260 }}>
        {/* Top Bar */}
        <header className="topbar">
          <div className="topbar-left">
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="hidden md:flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
              style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
            </button>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg"
              style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
              aria-label="Toggle mobile menu"
            >
              <PanelLeft size={16} />
            </button>

            {/* Breadcrumb */}
            {(() => {
              const exact = ROUTE_TITLES[location.pathname]
              const dynamic = !exact && location.pathname.startsWith('/incidents/')
                ? { label: 'Incident Detail', parent: 'Alerts' }
                : null
              const route = exact || dynamic
              return route ? (
                <div className="hidden md:flex items-center gap-1.5 px-2" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  <ChevronRight size={14} style={{ opacity: 0.4 }} />
                  {route.parent && (
                    <>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>{route.parent}</span>
                      <ChevronRight size={12} style={{ opacity: 0.4 }} />
                    </>
                  )}
                  <span style={{ color: 'var(--text-heading)', fontWeight: 700 }}>{route.label}</span>
                </div>
              ) : null
            })()}

            {/* Search */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg focus-within:ring-2 focus-within:ring-indigo-500/20 transition-shadow" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', minWidth: 300 }}>
              <Search size={14} style={{ color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search incidents..."
                aria-label="Search incidents"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQuery.trim()) {
                    navigate(`/alerts?search=${encodeURIComponent(searchQuery.trim())}`)
                  }
                }}
                className="focus:outline-none"
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--text-primary)',
                  fontSize: 12,
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => {
                    setSearchQuery('')
                    navigate('/alerts')
                  }}
                  className="p-1 rounded hover:bg-elevated transition-colors"
                  title="Clear search"
                  aria-label="Clear search"
                >
                  <X size={12} style={{ color: 'var(--text-muted)' }} />
                </button>
              )}
              <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>/</kbd>
            </div>
          </div>

          <div className="topbar-right">
            {/* Lead Approval - admin only */}
            {normalizeRole(user?.role || '') === 'admin' && (
              <button
                onClick={() => setShowLeadApproval(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-all hover-lift"
                style={{ background: 'rgba(251,191,36,0.12)', color: 'var(--color-accent-amber)', border: '1px solid rgba(245,158,11,0.25)' }}
                title="Lead Approval"
              >
                <ClipboardList size={14} />
                <span className="hidden lg:inline">Lead Approval</span>
              </button>
            )}

            {/* Status */}
            <div className="status-pill">
              <span className="status-dot status-dot-green" />
              <span>NOMINAL</span>
            </div>



            {/* Theme Toggle */}
            <div className="theme-toggle" onClick={toggle} role="button" tabIndex={0} aria-label="Toggle theme">
              <div className={`theme-toggle-option ${isDark ? 'active' : ''}`}>
                <Moon size={14} />
              </div>
              <div className={`theme-toggle-option ${!isDark ? 'active' : ''}`}>
                <Sun size={14} />
              </div>
            </div>

            {/* Notification bell */}
            <div className="relative">
              <button
                ref={bellRef}
                onClick={() => setShowNotifications(!showNotifications)}
                className="relative flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover-lift"
                style={{ color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
                aria-label="Toggle notifications"
              >
                {unreadCount > 0 ? <BellRing size={16} style={{ color: 'var(--color-accent-amber)' }} /> : <Bell size={16} />}
                {unreadCount > 0 && (
                  <span
                    className="absolute -top-1 -right-1 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[9px] font-bold"
                    style={{ background: 'var(--color-accent-red)', color: '#fff', lineHeight: 1 }}
                  >
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </button>

              {/* Notification Dropdown */}
              <AnimatePresence>
                {showNotifications && (
                  <Motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -6 }}
                    transition={{ duration: 0.15, ease: 'easeOut' }}
                    style={{ position: 'absolute', right: 0, top: 'calc(100% + 8px)', zIndex: 50, transformOrigin: 'top right' }}
                  >
                    <NotificationDropdown
                      ref={dropdownRef}
                      notifications={notifications}
                      unreadCount={unreadCount}
                      markAllRead={markAllRead}
                      onClose={() => setShowNotifications(false)}
                      onClickItem={(id) => {
                        setShowNotifications(false)
                        setNotifications(prev => {
                          const updated = prev.map(x => x.id === id ? { ...x, read: true } : x)
                          saveReadIds(new Set(updated.filter(x => x.read).map(x => x.id)))
                          return updated
                        })
                      }}
                    />
                  </Motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-6 overflow-auto">
          <div className="w-full">
            <AnimatePresence mode="wait" initial={false}>
              <Motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.18, ease: 'easeInOut' }}
              >
                {children}
              </Motion.div>
            </AnimatePresence>
          </div>
        </main>

        {/* Footer */}
        <footer className="py-4 px-6 relative">
          <div className="absolute top-0 left-0 right-0 divider-glow"></div>
          <div className="flex justify-between items-center" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
            <span>AIREX AUTONOMOUS SRE v0.9</span>
            <span className="flex items-center gap-2">
              <span className="status-dot status-dot-green inline-block"></span>
              STATUS: OPERATIONAL
            </span>
          </div>
        </footer>
      </div>

      {/* Toast Container */}
      <ToastContainer />

      {/* Lead Approval Panel */}
      <LeadApprovalPanel isOpen={showLeadApproval} onClose={() => setShowLeadApproval(false)} />

      {/* Mobile overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <Motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 z-30 md:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}


function WorkspaceRoleBadge({ membershipRole, active }) {
  const label = membershipRole ? membershipRole : 'inherited'
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 7px',
        borderRadius: 999,
        border: '1px solid',
        borderColor: membershipRole ? 'rgba(251,146,60,0.28)' : active ? 'rgba(34,211,238,0.28)' : 'var(--border)',
        color: membershipRole ? 'var(--brand-orange)' : active ? 'var(--neon-cyan)' : 'var(--text-muted)',
        background: membershipRole ? 'rgba(251,146,60,0.12)' : active ? 'rgba(34,211,238,0.08)' : 'rgba(255,255,255,0.03)',
        textTransform: 'capitalize',
      }}
    >
      {label}
    </span>
  )
}

function SidebarWorkspaceSwitcher({ organizations, activeOrganization, tenants, activeTenant, switchTenant, currentUserId, navigate, collapsed }) {
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(null)
  const [accessibleTenants, setAccessibleTenants] = useState([])
  const ref = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadAccessible() {
      if (!currentUserId) {
        setAccessibleTenants([])
        return
      }
      try {
        const rows = await fetchUserAccessibleTenants(currentUserId)
        if (!cancelled) {
          setAccessibleTenants(Array.isArray(rows) ? rows : [])
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Failed to load accessible tenants:', err)
          setAccessibleTenants([])
        }
      }
    }
    loadAccessible()
    return () => {
      cancelled = true
    }
  }, [currentUserId])

  const tenantDetailsMap = new Map((tenants || []).map((tenant) => [String(tenant.id), tenant]))
  const organizationMap = new Map((organizations || []).map((org) => [String(org.id), org]))
  const visibleTenants = accessibleTenants.map((tenant) => {
    const detail = tenantDetailsMap.get(String(tenant.id))
    const organization = organizationMap.get(String(tenant.organization_id))
    return {
      ...tenant,
      display_name: detail?.display_name || tenant.display_name,
      name: detail?.name || tenant.name,
      cloud: detail?.cloud || tenant.cloud,
      organization_name: detail?.organization_name || organization?.name || 'Organization',
      organization_slug: detail?.organization_slug || organization?.slug || '',
    }
  })

  const handleSwitch = async (tenant) => {
    if (String(tenant.id) === String(activeTenant?.id)) { setOpen(false); return }
    setSwitching(tenant.id)
    try {
      await switchTenant(tenant.id)
      navigate('/dashboard', { replace: false })
    } finally {
      setSwitching(null)
      setOpen(false)
    }
  }

  // Active display name
  const displayName = activeOrganization?.name || activeOrganization?.slug || 'Select Workspace'
  const initial = displayName.charAt(0).toUpperCase()

  return (
    <div className="relative" ref={ref} style={{ padding: collapsed ? '8px 6px' : '8px 12px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2.5 rounded-lg transition-all"
        style={{
          padding: collapsed ? '8px 0' : '8px 10px',
          justifyContent: collapsed ? 'center' : 'flex-start',
          background: open ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.03)',
          border: '1px solid',
          borderColor: open ? 'rgba(99,102,241,0.25)' : 'var(--border)',
          cursor: 'pointer',
          color: 'var(--text-primary)',
        }}
      >
        <div
          className="flex items-center justify-center flex-shrink-0 rounded-md"
          style={{
            width: 28, height: 28,
            background: 'var(--gradient-cyan)',
            color: '#fff', fontWeight: 700, fontSize: 12,
          }}
        >
          {initial}
        </div>
        {!collapsed && (
          <>
            <div className="flex flex-col min-w-0 flex-1 text-left" style={{ gap: 1 }}>
              <span className="truncate max-w-[130px]" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }} title={displayName}>
                {displayName}
              </span>
              {activeTenant && (
                <span className="truncate max-w-[130px]" style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--neon-cyan)', letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.8 }}>
                  {activeTenant.display_name || activeTenant.name}
                </span>
              )}
            </div>
            <ChevronRight size={12} style={{ color: 'var(--text-muted)', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s', flexShrink: 0 }} />
          </>
        )}
      </button>

      <AnimatePresence>
        {open && !collapsed && (
          <Motion.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.12, ease: 'easeOut' }}
            style={{
              position: 'absolute', top: 'calc(100% + 4px)', left: 12, zIndex: 60,
              width: 'calc(100% - 24px)', transformOrigin: 'top left',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.4)',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: '10px 12px 6px', borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
              <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Switch Workspace
              </span>
            </div>
            
            <div style={{ padding: 6, maxHeight: 300, overflowY: 'auto' }}>
              {visibleTenants.map(tenant => {
                const isActive = String(tenant.id) === String(activeTenant?.id)
                const isSwitching = switching === tenant.id
                return (
                  <button
                    key={tenant.id}
                    onClick={() => handleSwitch(tenant)}
                    disabled={isSwitching}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-left"
                    style={{
                      background: isActive ? 'rgba(34,211,238,0.06)' : 'transparent',
                      cursor: isActive ? 'default' : 'pointer',
                      opacity: isSwitching ? 0.6 : 1,
                    }}
                  >
                    <div
                      className="flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0"
                      style={{ background: isActive ? 'var(--gradient-cyan)' : 'var(--bg-input)', border: '1px solid var(--border)', color: isActive ? '#fff' : 'var(--text-muted)', fontWeight: 700, fontSize: 12 }}
                    >
                      {tenant.display_name ? tenant.display_name.charAt(0).toUpperCase() : <Building2 size={14} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div style={{ fontSize: 13, fontWeight: 600, color: isActive ? 'var(--neon-cyan)' : 'var(--text-heading)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {tenant.display_name || tenant.name}
                      </div>
                      <div style={{ fontSize: 11, fontFamily: 'var(--font-sans)', color: 'var(--text-muted)' }}>
                        {tenant.organization_name} · {tenant.cloud?.toUpperCase?.() || 'N/A'}
                      </div>
                    </div>
                    <WorkspaceRoleBadge membershipRole={tenant.membership_role} active={isActive} />
                    {isActive && <Check size={14} style={{ color: '#22d3ee', flexShrink: 0 }} />}
                  </button>
                )
              })}
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}


const NotificationDropdown = forwardRef(function NotificationDropdown(
  { notifications, unreadCount, markAllRead, onClose, onClickItem },
  ref
) {
  return (
    <div
      ref={ref}
      className="rounded-xl overflow-hidden z-50 glass backdrop-blur-xl"
      style={{
        width: 380,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
          Notifications
          {unreadCount > 0 && (
            <span className="ml-2 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold"
              style={{ background: 'var(--glow-rose)', color: 'var(--color-accent-red)' }}>
              {unreadCount}
            </span>
          )}
        </span>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              style={{ fontSize: 11, color: 'var(--neon-indigo)', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Mark all read
            </button>
          )}
          <button
            onClick={onClose}
            style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* List */}
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {notifications.length === 0 ? (
          <div className="py-10 text-center" style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            No notifications
          </div>
        ) : (
          notifications.map(n => (
            <Link
              key={n.id}
              to={`/incidents/${n.id}`}
              onClick={() => onClickItem(n.id)}
              className="notification-item flex items-start gap-3 px-4 py-3 transition-colors"
              style={{
                borderBottom: '1px solid var(--border)',
                background: n.read ? 'transparent' : 'rgba(99,102,241,0.03)',
              }}
            >
              <div className="flex-shrink-0 mt-1.5">
                {!n.read && ACTIVE_STATES.includes(n.state) ? (
                  <span className="block w-2 h-2 rounded-full" style={{ background: n.severity === 'CRITICAL' ? 'var(--color-accent-red)' : 'var(--neon-indigo)' }} />
                ) : (
                  <span className="block w-2 h-2 rounded-full" style={{ background: 'transparent' }} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="truncate" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>
                  {n.title}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="rounded px-1.5 py-0.5" style={{
                    fontSize: 9, fontWeight: 700,
                    background: n.severity === 'CRITICAL' ? 'rgba(244,63,94,0.12)' : n.severity === 'HIGH' ? 'rgba(251,146,60,0.12)' : 'rgba(148,163,184,0.1)',
                    color: n.severity === 'CRITICAL' ? 'var(--color-accent-red)' : n.severity === 'HIGH' ? 'var(--brand-orange)' : 'var(--text-muted)',
                  }}>
                    {n.severity}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                    {n.alert_type}
                  </span>
                  <span className="flex items-center gap-0.5" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                    <Clock size={9} />
                    {n.created_at ? new Date(n.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : ''}
                  </span>
                </div>
              </div>
              <div className="flex-shrink-0">
                {n.state === 'AWAITING_APPROVAL' ? (
                  <Zap size={14} style={{ color: 'var(--color-accent-amber)' }} />
                ) : (
                  <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
                )}
              </div>
            </Link>
          ))
        )}
      </div>

      {/* Footer */}
      <Link
        to="/alerts"
        onClick={onClose}
        className="notification-item block text-center py-2.5 transition-colors"
        style={{ borderTop: '1px solid var(--border)', fontSize: 12, fontWeight: 600, color: 'var(--neon-indigo)' }}
      >
        View all alerts
      </Link>
    </div>
  )
})
