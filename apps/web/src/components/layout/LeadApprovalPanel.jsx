import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Clock, CheckCircle, XCircle, ChevronRight, RefreshCcw, X } from 'lucide-react'
import { fetchIncidents, approveIncident, rejectIncident } from '../../services/api'
import { formatRelativeTime } from '../../utils/formatters'

const SEVERITY_COLOR = { CRITICAL: '#fb7185', HIGH: '#fb923c', MEDIUM: '#fbbf24', LOW: '#94a3b8' }
const SEVERITY_BG = { CRITICAL: 'rgba(251,113,133,0.12)', HIGH: 'rgba(251,146,60,0.12)', MEDIUM: 'rgba(251,191,36,0.12)', LOW: 'rgba(148,163,184,0.12)' }

export default function LeadApprovalPanel({ isOpen, onClose }) {
  const [pending, setPending] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchIncidents({ state: 'AWAITING_APPROVAL', limit: 50 })
      setPending((data.items || []).filter(i => !i.assigned_to))
    } catch (err) {
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
      await load()
    } catch (err) {
      alert('Approval failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionLoading(null)
    }
  }

  const handleReject = async (id) => {
    const reason = prompt('Rejection reason (optional):')
    if (reason === null) return
    setActionLoading(id)
    try {
      await rejectIncident(id, reason)
      await load()
    } catch (err) {
      alert('Rejection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionLoading(null)
    }
  }

  if (!isOpen) return null

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 h-full w-[420px] z-50 flex flex-col glass backdrop-blur-xl"
        style={{ background: 'var(--bg-card)', borderLeft: '1px solid var(--border)', boxShadow: '-10px 0 40px rgba(0,0,0,0.3)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-heading)' }}>Lead Approval</h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {pending.length} pending {pending.length === 1 ? 'incident' : 'incidents'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              disabled={loading}
              className="p-2 rounded-lg transition-colors hover:bg-elevated"
              style={{ color: 'var(--text-muted)' }}
              title="Refresh"
            >
              <RefreshCcw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg transition-colors hover:bg-elevated"
              style={{ color: 'var(--text-muted)' }}
              title="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            [1, 2, 3].map(i => (
              <div key={i} className="glass rounded-xl h-32 skeleton" />
            ))
          ) : pending.length === 0 ? (
            <div className="glass rounded-xl py-16 text-center flex flex-col items-center gap-3" style={{ color: 'var(--text-muted)' }}>
              <CheckCircle size={36} style={{ opacity: 0.4 }} />
              <p style={{ fontSize: 14, fontWeight: 600 }}>No pending approvals</p>
              <p style={{ fontSize: 12 }}>All caught up! Nothing needs your review.</p>
            </div>
          ) : (
            pending.map(inc => (
              <div key={inc.id} className="glass rounded-xl p-4 space-y-3" style={{ border: '1px solid var(--border)' }}>
                <Link to={`/incidents/${inc.id}`} className="block space-y-2 hover:opacity-80 transition-opacity">
                  <div className="flex items-start justify-between gap-2">
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', lineHeight: 1.4 }}>
                      {inc.title}
                    </span>
                    <span
                      className="flex-shrink-0"
                      style={{
                        background: SEVERITY_BG[inc.severity] || SEVERITY_BG.LOW,
                        color: SEVERITY_COLOR[inc.severity] || SEVERITY_COLOR.LOW,
                        borderRadius: 999,
                        padding: '2px 8px',
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      {inc.severity}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                      {inc.alert_type}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {formatRelativeTime(inc.created_at)}
                    </span>
                  </div>
                </Link>

                {/* Actions */}
                <div className="flex gap-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                  <button
                    onClick={() => handleApprove(inc.id)}
                    disabled={actionLoading === inc.id}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all"
                    style={{
                      background: actionLoading === inc.id ? 'var(--bg-input)' : 'rgba(34,197,94,0.15)',
                      color: actionLoading === inc.id ? 'var(--text-muted)' : '#22c55e',
                      border: '1px solid rgba(34,197,94,0.3)',
                    }}
                  >
                    <CheckCircle size={14} />
                    Approve
                  </button>
                  <button
                    onClick={() => handleReject(inc.id)}
                    disabled={actionLoading === inc.id}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all"
                    style={{
                      background: actionLoading === inc.id ? 'var(--bg-input)' : 'rgba(239,68,68,0.15)',
                      color: actionLoading === inc.id ? 'var(--text-muted)' : '#ef4444',
                      border: '1px solid rgba(239,68,68,0.3)',
                    }}
                  >
                    <XCircle size={14} />
                    Reject
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}
