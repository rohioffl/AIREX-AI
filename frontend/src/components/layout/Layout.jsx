import { useState, useEffect, useRef, forwardRef } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, AlertTriangle, Activity, Settings,
  Sun, Moon, Bell, BellRing, PanelLeftClose, PanelLeft, Search, LogOut,
  X, ChevronRight, Clock, Zap, Ban
} from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import { useAuth } from '../../context/AuthContext'
import { fetchIncidents } from '../../services/api'
import { createSSEConnection } from '../../services/sse'
import ToastContainer from '../common/ToastContainer'

const ACTIVE_STATES = [
  'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY',
  'AWAITING_APPROVAL', 'EXECUTING', 'VERIFYING',
]

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Alerts', path: '/alerts', icon: AlertTriangle, showBadge: true },
  { label: 'Rejected', path: '/rejected', icon: Ban },
  { label: 'Live Feed', path: '/live', icon: Activity },
  { label: 'Settings', path: '/settings', icon: Settings },
]

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { isDark, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const [criticalCount, setCriticalCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [showNotifications, setShowNotifications] = useState(false)
  const bellRef = useRef(null)
  const dropdownRef = useRef(null)

  const isActive = (path) => location.pathname.startsWith(path)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  // Load initial alert counts
  useEffect(() => {
    let cancelled = false
    async function loadAlerts() {
      try {
        const data = await fetchIncidents({ limit: 200 })
        if (cancelled) return
        const items = data.items || []
        const active = items.filter(i => ACTIVE_STATES.includes(i.state))
        setAlertCount(active.length)
        setCriticalCount(active.filter(i => i.severity === 'CRITICAL').length)
        setNotifications(active.slice(0, 10).map(i => ({
          id: i.id,
          title: i.title || 'Alert',
          severity: i.severity || 'MEDIUM',
          state: i.state || 'RECEIVED',
          alert_type: i.alert_type || 'unknown',
          created_at: i.created_at || '',
          read: false,
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
            setAlertCount(c => c + 1)
            if (data.severity === 'CRITICAL') setCriticalCount(c => c + 1)
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
              setAlertCount(c => Math.max(0, c - 1))
            }
            setNotifications(prev =>
              prev.map(n => n.id === data.incident_id ? { ...n, state: data.new_state } : n)
            )
          },
        },
        () => {}
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
  const markAllRead = () => setNotifications(prev => prev.map(n => ({ ...n, read: true })))

  const initials = user?.displayName
    ? user.displayName.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : user?.email
      ? user.email.substring(0, 2).toUpperCase()
      : 'OP'

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--bg-body)', color: 'var(--text-primary)' }}>
      {/* Sidebar */}
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'open' : ''}`}>
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="sidebar-brand-logo">A</div>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">AIREX</span>
            <span className="sidebar-brand-sub">autonomous sre</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          <div className="sidebar-section-label">
            <span className="sidebar-label">Navigation</span>
          </div>
          {NAV_ITEMS.map(item => (
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
                      background: criticalCount > 0 ? '#f43f5e' : '#fb923c',
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
            <div className="sidebar-avatar">{initials}</div>
            <div className="sidebar-footer-text">
              <span className="sidebar-user-name">{user?.email || 'Operator'}</span>
              <span className="sidebar-user-role">{user?.role || 'dev mode'}</span>
            </div>
            {user && (
              <button
                onClick={handleLogout}
                title="Sign out"
                className="sidebar-label"
                style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}
              >
                <LogOut size={14} />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-h-screen transition-[margin] duration-300" style={{ marginLeft: collapsed ? 64 : 240 }}>
        {/* Top Bar */}
        <header className="topbar">
          <div className="topbar-left">
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="hidden md:flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
              style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
            >
              {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
            </button>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg"
              style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
            >
              <PanelLeft size={16} />
            </button>

            {/* Search */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              <Search size={14} style={{ color: 'var(--text-muted)' }} />
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Search incidents...</span>
              <kbd className="ml-4 px-1.5 py-0.5 rounded text-[10px] font-mono" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>/</kbd>
            </div>
          </div>

          <div className="topbar-right">
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
                className="relative flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
                style={{ color: 'var(--text-muted)', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
              >
                {unreadCount > 0 ? <BellRing size={16} style={{ color: '#fbbf24' }} /> : <Bell size={16} />}
                {unreadCount > 0 && (
                  <span
                    className="absolute -top-1 -right-1 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[9px] font-bold"
                    style={{ background: '#f43f5e', color: '#fff', lineHeight: 1 }}
                  >
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </button>

              {/* Notification Dropdown */}
              {showNotifications && (
                <NotificationDropdown
                  ref={dropdownRef}
                  notifications={notifications}
                  unreadCount={unreadCount}
                  markAllRead={markAllRead}
                  onClose={() => setShowNotifications(false)}
                  onClickItem={(id) => {
                    setShowNotifications(false)
                    setNotifications(prev => prev.map(x => x.id === id ? { ...x, read: true } : x))
                  }}
                />
              )}
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-6 overflow-auto">
          <div className="max-w-[1400px] mx-auto">
            {children}
          </div>
        </main>

        {/* Footer */}
        <footer className="py-4 px-6" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="max-w-[1400px] mx-auto flex justify-between items-center" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
            <span>AIREX AUTONOMOUS SRE v0.9</span>
            <span>STATUS: OPERATIONAL</span>
          </div>
        </footer>
      </div>

      {/* Toast Container */}
      <ToastContainer />

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-30 md:hidden" onClick={() => setMobileOpen(false)} />
      )}
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
      className="absolute right-0 top-full mt-2 rounded-xl overflow-hidden z-50"
      style={{
        width: 380,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>
          Notifications
          {unreadCount > 0 && (
            <span className="ml-2 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold"
              style={{ background: 'rgba(244,63,94,0.15)', color: '#fb7185' }}>
              {unreadCount}
            </span>
          )}
        </span>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              style={{ fontSize: 11, color: '#818cf8', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer' }}
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
                  <span className="block w-2 h-2 rounded-full" style={{ background: n.severity === 'CRITICAL' ? '#f43f5e' : '#818cf8' }} />
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
                    color: n.severity === 'CRITICAL' ? '#fb7185' : n.severity === 'HIGH' ? '#fb923c' : '#94a3b8',
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
                  <Zap size={14} style={{ color: '#fbbf24' }} />
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
        style={{ borderTop: '1px solid var(--border)', fontSize: 12, fontWeight: 600, color: '#818cf8' }}
      >
        View all alerts
      </Link>
    </div>
  )
})
