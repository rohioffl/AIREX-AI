export default function ConfirmationModal({ open, title, message, onConfirm, onCancel }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} onClick={onCancel} />
      <div className="relative w-full max-w-md mx-4 glass rounded-2xl p-6 animate-slide-up glow-indigo">
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>{title}</h3>
        <p style={{ marginTop: 12, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{message}</p>
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
            className="rounded-lg px-5 py-2 text-sm font-semibold text-white transition-all"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 12px rgba(99,102,241,0.25)' }}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
