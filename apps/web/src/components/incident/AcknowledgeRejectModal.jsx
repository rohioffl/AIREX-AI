import { useState, useEffect } from 'react'
import { Mail, Ban, X } from 'lucide-react'
import { buildAcknowledgeMailto } from '../../utils/formatters'

export default function AcknowledgeRejectModal({
  open,
  incident,
  onAcknowledge,
  onReject,
  onCancel,
  loading = false,
  initialAction = null, // 'acknowledge' or 'reject' to skip selection
}) {
  const [rejectNote, setRejectNote] = useState('')
  const [action, setAction] = useState(initialAction) // 'acknowledge' or 'reject'

  // Reset action when modal closes
  useEffect(() => {
    if (!open) {
      const timer = setTimeout(() => {
        setAction(null)
        setRejectNote('')
      }, 300)
      return () => clearTimeout(timer)
    }
  }, [open])

  if (!open) return null

  const trimmedNote = rejectNote.trim()
  // Allow rejection even without a note; backend will
  // fall back to a generic manual reason if empty.
  const canReject = trimmedNote.length <= 500

  const handleAcknowledge = () => {
    if (incident) {
      // Avoid noopener/noreferrer — Gmail needs to follow auth redirects
      // which fail when the opener relationship is severed.
      window.open(buildAcknowledgeMailto(incident), '_blank')
    }
    if (onAcknowledge) {
      onAcknowledge()
    }
    onCancel()
  }

  const handleReject = () => {
    if (canReject && onReject) {
      onReject(trimmedNote)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div 
        className="absolute inset-0" 
        style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} 
        onClick={onCancel} 
      />
      <div 
        className="relative w-full max-w-lg mx-4 glass rounded-2xl p-6 animate-slide-up glow-indigo"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>
            {action === 'reject' ? 'Reject Alert' : action === 'acknowledge' ? 'Acknowledge Alert' : 'Action Required'}
          </h3>
          <button
            onClick={onCancel}
            className="p-1 rounded transition-colors"
            style={{ color: 'var(--text-muted)', background: 'var(--bg-input)' }}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '0.7'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
          >
            <X size={18} />
          </button>
        </div>

        {!action ? (
          <div className="space-y-3">
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 6 }}>
              Choose an action for this incident:
            </p>
            <button
              onClick={() => setAction('acknowledge')}
              className="w-full flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold text-white transition-all"
              style={{ 
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', 
                boxShadow: '0 4px 12px rgba(99,102,241,0.2)' 
              }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
            >
              <Mail size={16} />
              Acknowledge
            </button>
            <button
              onClick={() => setAction('reject')}
              className="w-full flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold transition-all"
              style={{ 
                color: 'var(--text-secondary)', 
                border: '1px solid var(--border)',
                background: 'var(--bg-elevated)'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-input)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'var(--bg-elevated)'}
            >
              <Ban size={16} />
              Reject
            </button>
          </div>
        ) : action === 'acknowledge' ? (
           <div className="space-y-4">
             <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
               You are about to acknowledge this alert and send a notification email to the on-call channel.
             </p>
             <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
               This will open a Gmail draft with incident details. You can review and send the acknowledgment.
             </p>
            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-all"
                style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleAcknowledge}
                disabled={loading}
                 className="flex-1 flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-60"
                style={{ 
                  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', 
                  boxShadow: '0 4px 12px rgba(99,102,241,0.2)' 
                }}
              >
                 <Mail size={14} />
                 Confirm Acknowledge
              </button>
            </div>
          </div>
        ) : (
           <div className="space-y-4">
             <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
               You are about to reject this alert and move it to the Rejected queue.
             </p>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                Optionally add a short note so future reviewers understand why this alert was rejected.
              </p>
            <div>
              <label 
                htmlFor="reject-note-modal" 
                style={{ 
                  fontSize: 12, 
                  fontWeight: 600, 
                  color: 'var(--text-secondary)', 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: 6
                }}
              >
                Add a rejection note
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{trimmedNote.length}/500</span>
              </label>
              <textarea
                id="reject-note-modal"
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value.slice(0, 500))}
                placeholder="Explain why this alert should not be processed..."
                rows={4}
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: 12,
                  border: '1px solid var(--border)',
                  background: 'var(--bg-input)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                  resize: 'vertical',
                  fontFamily: 'inherit',
                }}
                disabled={loading}
                autoFocus
              />
               <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                This note is optional but recommended; it will appear in the manual-review log.
               </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setAction(null)
                  setRejectNote('')
                }}
                className="flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-all"
                style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                disabled={loading}
              >
                Back
              </button>
              <button
                onClick={handleReject}
                disabled={loading || !canReject}
                 className="flex-1 flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-60"
                style={{ 
                  background: 'linear-gradient(135deg, #f87171, #ef4444)', 
                  boxShadow: '0 4px 12px rgba(248,113,113,0.35)' 
                }}
              >
                 <Ban size={14} />
                 {loading ? 'Processing...' : 'Confirm Reject'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
