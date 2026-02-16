import { useState, useEffect } from 'react'
import { AlertTriangle, AlertOctagon, Bell, X, Clock } from 'lucide-react'
import { useToasts } from '../../context/ToastContext'

const STATUS_MAP = {
  CRITICAL: { color: '#f43f5e', Icon: AlertOctagon },
  HIGH:     { color: '#f59e0b', Icon: AlertTriangle },
  MEDIUM:   { color: '#22d3ee', Icon: AlertTriangle },
  LOW:      { color: '#6366f1', Icon: Bell },
}

function Toast({ toast, onDismiss }) {
  const [exiting, setExiting] = useState(false)
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
    setExiting(true)
    setTimeout(() => onDismiss(toast.id), 300)
  }

  const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className={`toast ${exiting ? 'toast-exit' : ''}`} onClick={toast.onClick}>
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
    </div>
  )
}

export default function ToastContainer() {
  const { toasts, dismissToast } = useToasts()

  if (toasts.length === 0) return null

  return (
    <div className="toast-container">
      {toasts.map(t => (
        <Toast key={t.id} toast={t} onDismiss={dismissToast} />
      ))}
    </div>
  )
}
