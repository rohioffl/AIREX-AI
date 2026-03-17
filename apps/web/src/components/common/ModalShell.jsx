import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const MotionDiv = motion.div

export default function ModalShell({
  children,
  onClose,
  title,
  subtitle = null,
  maxWidth = 'max-w-md',
  panelClassName = '',
  panelStyle = undefined,
  open = true,
}) {
  const containerRef = useRef(null)
  const previousFocusRef = useRef(null)

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement
      containerRef.current?.focus()
    } else {
      if (previousFocusRef.current && typeof previousFocusRef.current.focus === 'function') {
        previousFocusRef.current.focus()
      }
    }
  }, [open])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <MotionDiv
            className="absolute inset-0"
            style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <MotionDiv
            ref={containerRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            className={`relative w-full ${maxWidth} mx-4 glass rounded-2xl p-6 ${panelClassName}`}
            style={panelStyle}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {(title || subtitle) && (
              <div className="mb-4">
                {title ? <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</h3> : null}
                {subtitle ? <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{subtitle}</div> : null}
              </div>
            )}
            {children}
          </MotionDiv>
        </div>
      )}
    </AnimatePresence>
  )
}
