import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const MotionDiv = motion.div

export default function ConfirmationModal({
  open,
  title,
  message,
  onConfirm,
  onCancel,
  confirmLabel = 'Confirm',
  confirmTone = 'primary',
  loading = false,
}) {
  const modalRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement
      modalRef.current?.focus()
    } else {
      previousFocusRef.current?.focus()
    }
  }, [open])

  const confirmStyles = confirmTone === 'danger'
    ? {
        background: 'linear-gradient(135deg, #f87171, #ef4444)',
        boxShadow: '0 4px 12px rgba(248,113,113,0.35)',
      }
    : {
        background: 'var(--gradient-primary)',
        boxShadow: '0 4px 12px rgba(99,102,241,0.25)',
      }

  const renderMessage = typeof message === 'string'
    ? <p style={{ marginTop: 12, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{message}</p>
    : <div style={{ marginTop: 12 }}>{message}</div>

  return (
    <AnimatePresence>
      {open && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog" 
          aria-modal="true" 
          aria-label={typeof title === 'string' ? title : 'Confirmation dialog'}
          ref={modalRef}
          tabIndex={-1}
          onKeyDown={e => {
            if (e.key === 'Escape' && !loading) onCancel()
          }}
        >
          <MotionDiv
            className="absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} 
            onClick={() => { if (!loading) onCancel() }} 
          />
          <MotionDiv
            className="relative w-full max-w-md glass rounded-2xl p-6 glow-indigo"
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
          >
            <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</h3>
            {renderMessage}
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={onCancel}
                disabled={loading}
                className="rounded-lg px-4 py-2 text-sm font-medium transition-all hover:bg-white/5"
                style={{ color: 'var(--text-secondary)' }}
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                disabled={loading}
                className="rounded-lg px-5 py-2 text-sm font-semibold text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed hover:brightness-110 active:scale-95"
                style={confirmStyles}
              >
                {loading ? 'Processing…' : confirmLabel}
              </button>
            </div>
          </MotionDiv>
        </div>
      )}
    </AnimatePresence>
  )
}
