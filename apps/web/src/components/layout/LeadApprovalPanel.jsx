import { useState, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle, XCircle, RefreshCcw, X, ChevronRight,
  Server, Zap, Shield, AlertTriangle, Clock, Loader2
} from 'lucide-react'
import { fetchIncidents, approveIncident, rejectIncident } from '../../services/api'
import { formatRelativeTime } from '../../utils/formatters'

const SEVERITY_MAP = {
  CRITICAL: { color: '#f43f5e', bg: 'rgba(244,63,94,0.10)', border: 'rgba(244,63,94,0.25)', icon: AlertTriangle },
  HIGH:     { color: '#fb923c', bg: 'rgba(251,146,60,0.10)', border: 'rgba(251,146,60,0.25)', icon: AlertTriangle },
  MEDIUM:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.25)', icon: Shield },
  LOW:      { color: '#94a3b8', bg: 'rgba(148,163,184,0.10)', border: 'rgba(148,163,184,0.25)', icon: Shield },
}

function ConfidenceBar({ value }) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#f43f5e'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 rounded-full" style={{ background: 'var(--bg-card)' }}>
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color, fontWeight: 700, minWidth: 28 }}>
        {pct}%
      </span>
    </div>
  )
}

function IncidentCard({ inc, onApprove, onReject, isActing }) {
  const [showReject, setShowReject] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  const sev = SEVERITY_MAP[inc.severity] || SEVERITY_MAP.LOW
  const SevIcon = sev.icon

  const handleRejectSubmit = () => {
    onReject(inc.id, rejectReason)
    setShowReject(false)
    setRejectReason('')
  }

  const recommendation = inc.recommendation || inc.meta?.recommendation
  const proposedAction = recommendation?.action_name || recommendation?.action || null
  const confidence = recommendation?.confidence ?? null
  const targetHost = inc.meta?.target_host || inc.source_ip || null

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.97 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="rounded-2xl overflow-hidden"
      style={{ border: `1px solid ${sev.border}`, background: 'var(--bg-card)' }}
    >
      {/* Severity accent bar */}
      <div style={{ height: 3, background: sev.color, opacity: 0.8 }} />

      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start gap-3">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
            style={{ background: sev.bg, color: sev.color }}
          >
            <SevIcon size={15} />
          </div>
          <div className="flex-1 min-w-0">
            <Link
              to={`/incidents/${inc.id}`}
              className="block transition-opacity hover:opacity-75"
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)', lineHeight: 1.35 }}>
                {inc.title}
              </div>
            </Link>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span
                className="inline-flex items-center px-1.5 py-0.5 rounded-full"
                style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', background: sev.bg, color: sev.color }}
              >
                {inc.severity}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                {inc.alert_type}
              </span>
              <span className="flex items-center gap-1" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                <Clock size={10} />
                {formatRelativeTime(inc.created_at)}
              </span>
            </div>
          </div>
          <Link
            to={`/incidents/${inc.id}`}
            className="flex-shrink-0 p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
            title="View incident"
          >
            <ChevronRight size={13} />
          </Link>
        </div>

        {/* Meta row */}
        {(proposedAction || targetHost) && (
          <div
            className="flex flex-wrap gap-2 px-3 py-2 rounded-xl"
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
          >
            {proposedAction && (
              <div className="flex items-center gap-1.5">
                <Zap size={11} style={{ color: 'var(--neon-indigo)' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)', fontWeight: 600 }}>
                  {proposedAction}
                </span>
              </div>
            )}
            {targetHost && (
              <div className="flex items-center gap-1.5">
                <Server size={11} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                  {targetHost}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Confidence */}
        {confidence != null && (
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>
              AI Confidence
            </div>
            <ConfidenceBar value={confidence} />
          </div>
        )}

        {/* Rejection reason input (inline) */}
        <AnimatePresence>
          {showReject && (
            <motion.div
              key="reject-form"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              style={{ overflow: 'hidden' }}
            >
              <div className="space-y-2 pt-1">
                <textarea
                  autoFocus
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  placeholder="Reason for rejection (optional)..."
                  rows={2}
                  className="w-full rounded-xl px-3 py-2 resize-none text-sm"
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid rgba(239,68,68,0.4)',
                    color: 'var(--text-primary)',
                    fontFamily: 'inherit',
                    fontSize: 12,
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && e.metaKey) handleRejectSubmit()
                    if (e.key === 'Escape') { setShowReject(false); setRejectReason('') }
                  }}
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleRejectSubmit}
                    disabled={isActing}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold transition-all"
                    style={{
                      background: 'rgba(239,68,68,0.15)',
                      color: '#ef4444',
                      border: '1px solid rgba(239,68,68,0.35)',
                    }}
                  >
                    {isActing ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />}
                    Confirm Reject
                  </button>
                  <button
                    onClick={() => { setShowReject(false); setRejectReason('') }}
                    className="px-3 py-2 rounded-xl text-xs font-semibold transition-colors"
                    style={{ background: 'var(--bg-input)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Action buttons */}
        {!showReject && (
          <div className="flex gap-2 pt-1">
            <motion.button
              onClick={() => onApprove(inc.id)}
              disabled={isActing}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm font-bold transition-all"
              style={{
                background: isActing ? 'var(--bg-input)' : 'rgba(34,197,94,0.13)',
                color: isActing ? 'var(--text-muted)' : '#22c55e',
                border: `1px solid ${isActing ? 'var(--border)' : 'rgba(34,197,94,0.35)'}`,
              }}
              whileHover={isActing ? {} : { scale: 1.02, background: 'rgba(34,197,94,0.2)' }}
              whileTap={isActing ? {} : { scale: 0.97 }}
            >
              {isActing ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
              Approve
            </motion.button>
            <motion.button
              onClick={() => setShowReject(true)}
              disabled={isActing}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm font-bold transition-all"
              style={{
                background: isActing ? 'var(--bg-input)' : 'rgba(239,68,68,0.10)',
                color: isActing ? 'var(--text-muted)' : '#ef4444',
                border: `1px solid ${isActing ? 'var(--border)' : 'rgba(239,68,68,0.3)'}`,
              }}
              whileHover={isActing ? {} : { scale: 1.02, background: 'rgba(239,68,68,0.18)' }}
              whileTap={isActing ? {} : { scale: 0.97 }}
            >
              <XCircle size={13} />
              Reject
            </motion.button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default function LeadApprovalPanel({ isOpen, onClose }) {
  const [pending, setPending] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchIncidents({ state: 'AWAITING_APPROVAL', limit: 50 })
      setPending(data.items || [])
    } catch (err) {
      setError('Failed to load approval queue')
      console.warn('Failed to load approval queue:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen) load()
  }, [isOpen, load])

  const handleApprove = async (id) => {
    setActionLoading(id)
    try {
      await approveIncident(id, 'execute', `approve-${id}-${Date.now()}`)
      setPending(prev => prev.filter(i => i.id !== id))
    } catch (err) {
      setError('Approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionLoading(null)
    }
  }

  const handleReject = async (id, reason) => {
    setActionLoading(id)
    try {
      await rejectIncident(id, reason)
      setPending(prev => prev.filter(i => i.id !== id))
    } catch (err) {
      setError('Rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            className="fixed top-0 right-0 h-full z-50 flex flex-col"
            style={{
              width: 'min(440px, 95vw)',
              background: 'var(--bg-card)',
              borderLeft: '1px solid var(--border)',
              boxShadow: '-20px 0 60px rgba(0,0,0,0.35)',
            }}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4 flex-shrink-0"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <div
                    className="h-6 w-6 rounded-md flex items-center justify-center"
                    style={{ background: 'rgba(99,102,241,0.12)', color: 'var(--neon-indigo)' }}
                  >
                    <Shield size={13} />
                  </div>
                  <h2 style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-heading)' }}>
                    Lead Approval
                  </h2>
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', paddingLeft: 32 }}>
                  {loading ? 'Loading…' : `${pending.length} pending ${pending.length === 1 ? 'incident' : 'incidents'}`}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <motion.button
                  onClick={load}
                  disabled={loading}
                  className="p-2 rounded-lg"
                  style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
                  title="Refresh"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <RefreshCcw size={14} className={loading ? 'animate-spin' : ''} />
                </motion.button>
                <motion.button
                  onClick={onClose}
                  className="p-2 rounded-lg"
                  style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
                  title="Close"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <X size={15} />
                </motion.button>
              </div>
            </div>

            {/* Error banner */}
            <AnimatePresence>
              {error && (
                <motion.div
                  key="error"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="px-5 py-3 flex items-center justify-between gap-2"
                  style={{ background: 'rgba(239,68,68,0.08)', borderBottom: '1px solid rgba(239,68,68,0.2)' }}
                >
                  <span style={{ fontSize: 12, color: '#ef4444' }}>{error}</span>
                  <button onClick={() => setError(null)} style={{ color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer' }}>
                    <X size={13} />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {loading ? (
                // Skeleton cards
                [1, 2, 3].map(i => (
                  <motion.div
                    key={i}
                    className="rounded-2xl"
                    style={{ height: 160, background: 'var(--bg-input)', border: '1px solid var(--border)' }}
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut', delay: i * 0.15 }}
                  />
                ))
              ) : pending.length === 0 ? (
                <motion.div
                  key="empty"
                  className="flex flex-col items-center justify-center py-20 text-center"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3 }}
                >
                  <motion.div
                    className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4"
                    style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e' }}
                    animate={{ scale: [1, 1.06, 1] }}
                    transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
                  >
                    <CheckCircle size={32} />
                  </motion.div>
                  <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 6 }}>
                    All clear!
                  </p>
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 240, lineHeight: 1.5 }}>
                    No incidents are awaiting your approval right now.
                  </p>
                </motion.div>
              ) : (
                <AnimatePresence mode="popLayout">
                  {pending.map(inc => (
                    <IncidentCard
                      key={inc.id}
                      inc={inc}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      isActing={actionLoading === inc.id}
                    />
                  ))}
                </AnimatePresence>
              )}
            </div>

            {/* Footer */}
            {!loading && pending.length > 0 && (
              <div
                className="flex-shrink-0 px-5 py-3 flex items-center justify-between"
                style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-input)' }}
              >
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Review each incident carefully before approving
                </span>
                <span
                  className="px-2 py-0.5 rounded-full"
                  style={{ fontSize: 10, fontWeight: 700, background: 'rgba(99,102,241,0.12)', color: 'var(--neon-indigo)', fontFamily: 'var(--font-mono)' }}
                >
                  {pending.length}
                </span>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
