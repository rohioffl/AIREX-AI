import { X, Search, CheckCircle, XCircle, HelpCircle, Plus, Users, Escape } from 'lucide-react'

export default function KeyboardShortcutsModal({ onClose }) {
  const shortcuts = [
    { key: '/', description: 'Focus search bar', icon: Search },
    { key: 'a', description: 'Approve incident (on detail page)', icon: CheckCircle },
    { key: 'r', description: 'Reject incident (on detail page)', icon: XCircle },
    { key: 'n', description: 'New incident (on alerts page)', icon: Plus },
    { key: 'u', description: 'User management (admin only)', icon: Users },
    { key: '?', description: 'Show this help modal', icon: HelpCircle },
    { key: 'Esc', description: 'Close modals/dropdowns', icon: Escape },
  ]

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in"
      onClick={onClose}
      style={{ animationDuration: '0.2s' }}
    >
      <div
        className="glass rounded-xl p-6 w-full max-w-md shadow-2xl border border-border/50"
        onClick={(e) => e.stopPropagation()}
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
          {shortcuts.map((shortcut) => {
            const Icon = shortcut.icon
            return (
              <div
                key={shortcut.key}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-input transition-colors"
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
              </div>
            )
          })}
        </div>

        <div className="mt-6 pt-4 border-t border-border">
          <p className="text-xs text-muted text-center">
            Press <kbd className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>?</kbd> again to close
          </p>
        </div>
      </div>
    </div>
  )
}
