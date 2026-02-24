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
  if (!open) return null

  const confirmStyles = confirmTone === 'danger'
    ? {
        background: 'linear-gradient(135deg, #f87171, #ef4444)',
        boxShadow: '0 4px 12px rgba(248,113,113,0.35)',
      }
    : {
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        boxShadow: '0 4px 12px rgba(99,102,241,0.25)',
      }

  const renderMessage = typeof message === 'string'
    ? <p style={{ marginTop: 12, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{message}</p>
    : <div style={{ marginTop: 12 }}>{message}</div>

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={onCancel} />
      <div className="relative w-full max-w-md mx-4 glass rounded-2xl p-6 animate-slide-up glow-indigo">
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</h3>
        {renderMessage}
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-sm font-medium transition-all"
            style={{ color: 'var(--text-secondary)' }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="rounded-lg px-5 py-2 text-sm font-semibold text-white transition-all disabled:opacity-60"
            style={confirmStyles}
          >
            {loading ? 'Processing…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
