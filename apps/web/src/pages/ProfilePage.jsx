import { motion as Motion } from 'framer-motion'
import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  User, Mail, Shield, Key, LogOut, Copy, Check,
  ChevronRight, Calendar, Hash, ExternalLink,
  Bell, Send, ChevronDown, ChevronUp, Loader2,
  CheckCircle2, XCircle, Link2,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
  testNotification,
  fetchDeliveryLog,
} from '../services/api'

function InfoRow({ icon: Icon, label, value, mono, copyable }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl"
      style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
    >
      <div
        className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: 'var(--bg-card)', color: 'var(--neon-indigo)' }}
      >
        <Icon size={15} />
      </div>
      <div className="flex-1 min-w-0">
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 2 }}>
          {label}
        </div>
        <div style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--text-primary)',
          fontFamily: mono ? 'var(--font-mono)' : undefined,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {value || '—'}
        </div>
      </div>
      {copyable && value && (
        <button
          onClick={handleCopy}
          className="flex-shrink-0 p-1.5 rounded-md transition-colors"
          style={{ color: copied ? 'var(--color-accent-green)' : 'var(--text-muted)', background: 'var(--bg-card)' }}
          title="Copy"
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
        </button>
      )}
    </div>
  )
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className="relative inline-flex flex-shrink-0 rounded-full transition-colors"
      style={{
        width: 36,
        height: 20,
        background: checked ? 'var(--neon-indigo)' : 'var(--bg-input)',
        border: `1px solid ${checked ? 'var(--neon-indigo)' : 'var(--border)'}`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <span
        className="inline-block rounded-full bg-white transition-transform"
        style={{
          width: 14,
          height: 14,
          margin: 2,
          transform: checked ? 'translateX(16px)' : 'translateX(0)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
        }}
      />
    </button>
  )
}

function ToggleRow({ label, description, checked, onChange, disabled }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div className="flex-1 min-w-0">
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{label}</div>
        {description && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{description}</div>
        )}
      </div>
      <Toggle checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  )
}

const STATE_LABELS = [
  { key: 'notify_on_received',              label: 'Received',              description: 'New alert arrives' },
  { key: 'notify_on_investigating',         label: 'Investigating',         description: 'Investigation starts' },
  { key: 'notify_on_recommendation_ready',  label: 'Recommendation Ready',  description: 'AI generates a fix' },
  { key: 'notify_on_awaiting_approval',     label: 'Awaiting Approval',     description: 'Approval needed' },
  { key: 'notify_on_executing',             label: 'Executing',             description: 'Remediation running' },
  { key: 'notify_on_verifying',             label: 'Verifying',             description: 'Verification phase' },
  { key: 'notify_on_resolved',              label: 'Resolved',              description: 'Incident closed' },
  { key: 'notify_on_rejected',              label: 'Rejected',              description: 'Operator rejected' },
  { key: 'notify_on_failed',                label: 'Failed',                description: 'Any failure state' },
]

const STATUS_COLOR = {
  sent:   { color: '#22c55e', bg: 'rgba(34,197,94,0.1)',   icon: CheckCircle2 },
  failed: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   icon: XCircle },
}

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [prefs, setPrefs]               = useState(null)
  const [prefsSaving, setPrefsSaving]   = useState(false)
  const [slackUrl, setSlackUrl]         = useState('')
  const [testingNotif, setTestingNotif] = useState(false)
  const [testResult, setTestResult]     = useState(null)
  const [showLog, setShowLog]           = useState(false)
  const [deliveryLog, setDeliveryLog]   = useState([])
  const [logLoading, setLogLoading]     = useState(false)

  useEffect(() => {
    fetchNotificationPreferences()
      .then(data => {
        setPrefs(data)
        setSlackUrl(data.slack_webhook_url || '')
      })
      .catch(() => {})
  }, [])

  const togglePref = async (key, value) => {
    if (!prefs) return
    const updated = { ...prefs, [key]: value }
    setPrefs(updated)
    setPrefsSaving(true)
    try {
      const saved = await updateNotificationPreferences({ [key]: value })
      setPrefs(saved)
    } catch {
      setPrefs(prefs)
    } finally {
      setPrefsSaving(false)
    }
  }

  const saveSlackUrl = async () => {
    if (!prefs) return
    setPrefsSaving(true)
    try {
      const saved = await updateNotificationPreferences({ slack_webhook_url: slackUrl || null })
      setPrefs(saved)
      setSlackUrl(saved.slack_webhook_url || '')
    } finally {
      setPrefsSaving(false)
    }
  }

  const handleTestNotification = async () => {
    setTestingNotif(true)
    setTestResult(null)
    try {
      const res = await testNotification()
      setTestResult({ ok: true, message: res.message })
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Test failed'
      setTestResult({ ok: false, message: detail })
    } finally {
      setTestingNotif(false)
    }
  }

  const loadDeliveryLog = async () => {
    if (showLog) { setShowLog(false); return }
    setShowLog(true)
    setLogLoading(true)
    try {
      const logs = await fetchDeliveryLog(20)
      setDeliveryLog(logs)
    } catch {
      setDeliveryLog([])
    } finally {
      setLogLoading(false)
    }
  }

  const displayName = user?.email
    ? user.email.split('@')[0].replace(/[._-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : 'Operator'

  const initials = displayName
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  const roleColors = {
    admin:    { bg: 'rgba(99,102,241,0.12)', color: '#818cf8', border: 'rgba(99,102,241,0.3)' },
    operator: { bg: 'rgba(34,197,94,0.10)',  color: '#22c55e', border: 'rgba(34,197,94,0.3)' },
    viewer:   { bg: 'rgba(148,163,184,0.1)', color: '#94a3b8', border: 'rgba(148,163,184,0.3)' },
  }
  const roleStyle = roleColors[user?.role?.toLowerCase()] || roleColors.viewer

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen flex items-start justify-center py-10 px-4">
      <Motion.div
        className="w-full max-w-lg"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 mb-6" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          <span>Account</span>
          <ChevronRight size={13} style={{ opacity: 0.4 }} />
          <span style={{ color: 'var(--text-heading)', fontWeight: 600 }}>Profile</span>
        </div>

        {/* Avatar + Name Card */}
        <Motion.div
          className="glass rounded-2xl p-6 mb-4 text-center relative overflow-hidden"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.05, ease: 'easeOut' }}
        >
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: 'radial-gradient(ellipse 60% 40% at 50% 0%, rgba(99,102,241,0.08), transparent)',
            }}
          />

          <Motion.div
            className="mx-auto mb-4 flex items-center justify-center rounded-2xl text-2xl font-bold relative"
            style={{
              width: 72,
              height: 72,
              background: 'linear-gradient(135deg, var(--neon-indigo), #7c3aed)',
              color: '#fff',
              boxShadow: '0 8px 24px rgba(99,102,241,0.35)',
              fontFamily: 'var(--font-mono)',
            }}
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.1 }}
          >
            {initials}
          </Motion.div>

          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', marginBottom: 4 }}>
            {displayName}
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
            {user?.email}
          </p>

          <span
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full"
            style={{
              fontSize: 11,
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.07em',
              background: roleStyle.bg,
              color: roleStyle.color,
              border: `1px solid ${roleStyle.border}`,
            }}
          >
            <Shield size={11} />
            {user?.role || 'viewer'}
          </span>
        </Motion.div>

        {/* Info Section */}
        <Motion.div
          className="glass rounded-2xl p-4 mb-4 space-y-2"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15 }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '0 4px 8px' }}>
            Account Info
          </div>
          <InfoRow icon={User}     label="Display Name" value={displayName} />
          <InfoRow icon={Mail}     label="Email"        value={user?.email}     copyable />
          <InfoRow icon={Shield}   label="Role"         value={user?.role || 'viewer'} />
          <InfoRow icon={Hash}     label="User ID"      value={user?.userId}    mono copyable />
          <InfoRow icon={Calendar} label="Workspace ID" value={user?.tenantId} mono copyable />
        </Motion.div>

        {/* Actions */}
        <Motion.div
          className="glass rounded-2xl overflow-hidden mb-4"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.22 }}
        >
          <Link
            to="/set-password"
            className="flex items-center gap-3 px-5 py-4 transition-colors"
            style={{ borderBottom: '1px solid var(--border)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-input)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--neon-indigo)' }}>
              <Key size={15} />
            </div>
            <div className="flex-1">
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Change Password</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Update your account password</div>
            </div>
            <ExternalLink size={14} style={{ color: 'var(--text-muted)' }} />
          </Link>

          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-5 py-4 w-full text-left transition-colors"
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.06)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
              <LogOut size={15} />
            </div>
            <div className="flex-1">
              <div style={{ fontSize: 14, fontWeight: 600, color: '#ef4444' }}>Sign Out</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>End your current session</div>
            </div>
          </button>
        </Motion.div>

        {/* Notification Preferences */}
        <Motion.div
          className="glass rounded-2xl p-4 mb-4"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.28 }}
        >
          {/* Section header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Bell size={14} style={{ color: 'var(--neon-indigo)' }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Notifications
              </span>
            </div>
            {prefsSaving && <Loader2 size={13} style={{ color: 'var(--text-muted)', animation: 'spin 1s linear infinite' }} />}
          </div>

          {!prefs ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 size={18} style={{ color: 'var(--text-muted)', animation: 'spin 1s linear infinite' }} />
            </div>
          ) : (
            <div className="space-y-5">
              {/* Email */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Email</div>
                <div
                  className="rounded-xl px-4 py-1 space-y-1"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
                >
                  <ToggleRow
                    label="Enable email notifications"
                    checked={prefs.email_enabled}
                    onChange={v => togglePref('email_enabled', v)}
                    disabled={prefsSaving}
                  />
                  <div style={{ height: 1, background: 'var(--border)', margin: '0 -4px' }} />
                  <ToggleRow
                    label="Critical incidents only"
                    description="Skip LOW and MEDIUM severity"
                    checked={prefs.email_critical_only}
                    onChange={v => togglePref('email_critical_only', v)}
                    disabled={prefsSaving || !prefs.email_enabled}
                  />
                </div>
              </div>

              {/* Slack */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Slack</div>
                <div
                  className="rounded-xl px-4 py-1 space-y-1"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
                >
                  <ToggleRow
                    label="Enable Slack notifications"
                    checked={prefs.slack_enabled}
                    onChange={v => togglePref('slack_enabled', v)}
                    disabled={prefsSaving}
                  />
                  <div style={{ height: 1, background: 'var(--border)', margin: '0 -4px' }} />
                  <ToggleRow
                    label="Critical incidents only"
                    description="Skip LOW and MEDIUM severity"
                    checked={prefs.slack_critical_only}
                    onChange={v => togglePref('slack_critical_only', v)}
                    disabled={prefsSaving || !prefs.slack_enabled}
                  />
                </div>

                {/* Webhook URL input */}
                <div className="flex gap-2 mt-2">
                  <div className="flex-1 flex items-center gap-2 px-3 rounded-xl" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', height: 36 }}>
                    <Link2 size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                    <input
                      type="url"
                      placeholder="https://hooks.slack.com/services/…"
                      value={slackUrl}
                      onChange={e => setSlackUrl(e.target.value)}
                      style={{
                        flex: 1,
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        fontSize: 12,
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    />
                  </div>
                  <button
                    onClick={saveSlackUrl}
                    disabled={prefsSaving}
                    className="px-3 rounded-xl text-xs font-semibold transition-opacity"
                    style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--neon-indigo)', border: '1px solid rgba(99,102,241,0.3)', height: 36, opacity: prefsSaving ? 0.5 : 1 }}
                  >
                    Save
                  </button>
                </div>
              </div>

              {/* Per-state toggles */}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
                  Notify on State Change
                </div>
                <div
                  className="rounded-xl px-4 py-1"
                  style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
                >
                  {STATE_LABELS.map((item, idx) => (
                    <div key={item.key}>
                      <ToggleRow
                        label={item.label}
                        description={item.description}
                        checked={prefs[item.key]}
                        onChange={v => togglePref(item.key, v)}
                        disabled={prefsSaving}
                      />
                      {idx < STATE_LABELS.length - 1 && (
                        <div style={{ height: 1, background: 'var(--border)', margin: '0 -4px' }} />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Test notification */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleTestNotification}
                  disabled={testingNotif || (!prefs.email_enabled && !prefs.slack_enabled)}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-opacity"
                  style={{
                    background: 'rgba(99,102,241,0.15)',
                    color: 'var(--neon-indigo)',
                    border: '1px solid rgba(99,102,241,0.3)',
                    opacity: (testingNotif || (!prefs.email_enabled && !prefs.slack_enabled)) ? 0.5 : 1,
                  }}
                >
                  {testingNotif
                    ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                    : <Send size={14} />
                  }
                  Send Test
                </button>

                {testResult && (
                  <div
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
                    style={{
                      background: testResult.ok ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      color: testResult.ok ? '#22c55e' : '#ef4444',
                      border: `1px solid ${testResult.ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                    }}
                  >
                    {testResult.ok
                      ? <CheckCircle2 size={13} />
                      : <XCircle size={13} />
                    }
                    {testResult.message}
                  </div>
                )}
              </div>
            </div>
          )}
        </Motion.div>

        {/* Delivery Log */}
        <Motion.div
          className="glass rounded-2xl overflow-hidden mb-4"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.33 }}
        >
          <button
            onClick={loadDeliveryLog}
            className="flex items-center gap-3 w-full px-4 py-3 text-left transition-colors"
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-input)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div className="h-7 w-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--neon-indigo)' }}>
              <Bell size={13} />
            </div>
            <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Notification Delivery Log
            </span>
            {showLog ? <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />}
          </button>

          {showLog && (
            <div style={{ borderTop: '1px solid var(--border)' }}>
              {logLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 size={16} style={{ color: 'var(--text-muted)', animation: 'spin 1s linear infinite' }} />
                </div>
              ) : deliveryLog.length === 0 ? (
                <div className="py-6 text-center" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  No notifications sent yet
                </div>
              ) : (
                <div className="divide-y" style={{ '--tw-divide-color': 'var(--border)' }}>
                  {deliveryLog.map(entry => {
                    const s = STATUS_COLOR[entry.status] || STATUS_COLOR.failed
                    const StatusIcon = s.icon
                    return (
                      <div key={entry.id} className="flex items-start gap-3 px-4 py-3">
                        <div className="flex-shrink-0 mt-0.5 h-6 w-6 rounded-full flex items-center justify-center" style={{ background: s.bg }}>
                          <StatusIcon size={13} style={{ color: s.color }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className="px-1.5 py-0.5 rounded text-xs font-semibold uppercase"
                              style={{ background: 'var(--bg-input)', color: 'var(--text-muted)', border: '1px solid var(--border)', letterSpacing: '0.05em' }}
                            >
                              {entry.channel}
                            </span>
                            {entry.state_transition && (
                              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                {entry.state_transition}
                              </span>
                            )}
                          </div>
                          {entry.error_message && (
                            <div style={{ fontSize: 11, color: '#ef4444', marginTop: 2 }}>{entry.error_message}</div>
                          )}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0, marginTop: 2 }}>
                          {new Date(entry.delivered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </Motion.div>

        {/* Version footer */}
        <p className="text-center" style={{ fontSize: 11, color: 'var(--text-muted)', opacity: 0.5 }}>
          AIREX Autonomous SRE Platform
        </p>
      </Motion.div>
    </div>
  )
}
