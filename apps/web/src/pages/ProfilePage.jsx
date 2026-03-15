import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  User, Mail, Shield, Key, LogOut, Copy, Check,
  ChevronRight, Calendar, Hash, ExternalLink
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

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

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

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
      <motion.div
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
        <motion.div
          className="glass rounded-2xl p-6 mb-4 text-center relative overflow-hidden"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.05, ease: 'easeOut' }}
        >
          {/* Background glow */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: 'radial-gradient(ellipse 60% 40% at 50% 0%, rgba(99,102,241,0.08), transparent)',
            }}
          />

          {/* Avatar */}
          <motion.div
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
          </motion.div>

          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-heading)', marginBottom: 4 }}>
            {displayName}
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
            {user?.email}
          </p>

          {/* Role badge */}
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
        </motion.div>

        {/* Info Section */}
        <motion.div
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
          <InfoRow icon={Calendar} label="Tenant ID"    value={user?.tenantId}  mono copyable />
        </motion.div>

        {/* Actions */}
        <motion.div
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
        </motion.div>

        {/* Version footer */}
        <p className="text-center" style={{ fontSize: 11, color: 'var(--text-muted)', opacity: 0.5 }}>
          AIREX Autonomous SRE Platform
        </p>
      </motion.div>
    </div>
  )
}
