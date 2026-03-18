import { useEffect, useRef } from 'react'
import { X, Search, CheckCircle, XCircle, HelpCircle, Plus, Users } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const MotionDiv = motion.div

export default function KeyboardShortcutsModal({ onClose, open = true }) {
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

  const shortcuts = [
    { key: '/', description: 'Focus search bar', icon: Search },
    { key: 'a', description: 'Approve incident (on detail page)', icon: CheckCircle },
    { key: 'r', description: 'Reject incident (on detail page)', icon: XCircle },
    { key: 'n', description: 'New incident (on alerts page)', icon: Plus },
    { key: 'u', description: 'User management (admin only)', icon: Users },
    { key: '?', description: 'Show this help modal', icon: HelpCircle },
    { key: 'Esc', description: 'Close modals/dropdowns', icon: X },
  ]

  return (
    <AnimatePresence>
      {open && (
        <div
          ref={modalRef}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          aria-label="Keyboard Shortcuts"
          className="fixed inset-0 flex items-center justify-center z-50"
          onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
        >
          <MotionDiv
            className="absolute inset-0"
            style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(6px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <MotionDiv
            className="glass rounded-xl p-6 w-full max-w-md shadow-2xl border border-border/50 relative"
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold" style={{ color: 'var(--text-heading)' }}>
                Keyboard Shortcuts
              </h2>
              <button
                onClick={onClose}
                className="p-1 rounded-lg hover:bg-input transition-colors"
                title="Close (Esc)"
              >
                <X size={20} className="text-muted" />
              </button>
            </div>

            <div className="space-y-2">
              {shortcuts.map((shortcut, index) => {
                const Icon = shortcut.icon
                return (
                  <MotionDiv
                    key={shortcut.key}
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-input transition-colors"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03, duration: 0.2 }}
                  >
                    <div className="flex-shrink-0">
                      <Icon size={18} className="text-indigo-400" />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm" style={{ color: 'var(--text-primary)' }}>
                        {shortcut.description}
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      <kbd
                        className="px-2 py-1 rounded text-xs font-mono font-semibold"
                        style={{
                          background: 'var(--bg-input)',
                          border: '1px solid var(--border)',
                          color: 'var(--text-heading)',
                        }}
                      >
                        {shortcut.key}
                      </kbd>
                    </div>
                  </MotionDiv>
                )
              })}
            </div>

            <div className="mt-6 pt-4 border-t border-border">
              <p className="text-xs text-muted text-center">
                Press <kbd className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>?</kbd> again to close
              </p>
            </div>
          </MotionDiv>
        </div>
      )}
    </AnimatePresence>
  )
}
