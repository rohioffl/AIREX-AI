import StateBadge from '../common/StateBadge'
import { formatTimestamp } from '../../utils/formatters'
import { ArrowRight } from 'lucide-react'

export default function Timeline({ transitions }) {
  if (!transitions || transitions.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>No state transitions recorded.</p>
  }

  return (
    <div className="relative">
      <div className="absolute left-[11px] top-2 bottom-2 w-px" style={{ background: 'linear-gradient(to bottom, #6366f1 0%, var(--border) 50%, transparent 100%)' }} />
      <div className="space-y-4">
        {transitions.map((t, i) => (
          <div key={t.id} className="relative flex gap-4 group">
            <div className="relative z-10 mt-1.5">
              <div
                className="h-[9px] w-[9px] rounded-full border-2 transition-all"
                style={i === transitions.length - 1
                  ? { 
                      borderColor: '#6366F1', 
                      background: '#6366F1', 
                      borderWidth: document.body.classList.contains('light-mode') ? '2.5px' : '2px',
                      boxShadow: document.body.classList.contains('light-mode') 
                        ? '0 0 0 4px rgba(99,102,241,0.15)' 
                        : '0 0 8px rgba(129,140,248,0.4)' 
                    }
                  : { 
                      borderColor: 'var(--text-muted)', 
                      background: 'var(--bg-elevated)',
                      borderWidth: document.body.classList.contains('light-mode') ? '2px' : '2px'
                    }
                }
              />
            </div>
            <div className="flex-1 min-w-0 pb-1">
              <div className="flex items-center gap-2 flex-wrap">
                <StateBadge state={t.from_state} />
                <ArrowRight size={12} style={{ color: 'var(--text-muted)' }} />
                <StateBadge state={t.to_state} />
              </div>
              <p className="mt-1.5 truncate" style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {t.reason || 'No reason provided'}
              </p>
              <div className="mt-1 flex items-center gap-3" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                <span>{t.actor}</span>
                <span>&middot;</span>
                <span>{formatTimestamp(t.created_at)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
