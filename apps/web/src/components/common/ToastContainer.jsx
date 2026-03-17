import { useState, useEffect } from 'react'
import { AlertTriangle, AlertOctagon, Bell, X, Clock } from 'lucide-react'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { useToasts } from '../../context/ToastContext'

const STATUS_MAP = {
  CRITICAL: { color: 'var(--color-accent-red)', Icon: AlertOctagon },
  HIGH:     { color: 'var(--color-accent-amber)', Icon: AlertTriangle },
  MEDIUM:   { color: 'var(--neon-cyan)', Icon: AlertTriangle },
  LOW:      { color: 'var(--neon-indigo)', Icon: Bell },
}

function Toast({ toast, onDismiss }) {
  const [progress, setProgress] = useState(100)

  const severity = toast.severity || 'MEDIUM'
  const { color, Icon } = STATUS_MAP[severity] || STATUS_MAP.MEDIUM

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress(p => Math.max(0, p - (100 / 6000) * 50))
    }, 50)
    return () => clearInterval(interval)
  }, [])

  const handleDismiss = (e) => {
    e.stopPropagation()
    onDismiss(toast.id)
  }

  const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <Motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.92 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.92 }}
      transition={{ type: 'spring', stiffness: 480, damping: 38 }}
      className="toast"
      onClick={toast.onClick}
    >
      <div className="toast-accent" style={{ background: color }} />
      <div className="toast-icon" style={{ color }}>
        <Icon size={18} />
      </div>
      <div className="toast-body">
        <div className="toast-title">{toast.title || 'Alert'}</div>
        <div className="toast-message">{toast.message || ''}</div>
        <div className="toast-time">
          <Clock size={10} />
          {formatTime(toast.createdAt)}
        </div>
      </div>
      <button className="toast-close" onClick={handleDismiss} aria-label="Dismiss">
        <X size={14} />
      </button>
      <div className="toast-progress">
        <div className="toast-progress-bar" style={{ width: `${progress}%`, background: color }} />
      </div>
    </Motion.div>
  )
}

export default function ToastContainer() {
  const { toasts, dismissToast } = useToasts()

  return (
    <div className="toast-container">
      <AnimatePresence mode="popLayout">
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onDismiss={dismissToast} />
        ))}
      </AnimatePresence>
    </div>
  )
}
