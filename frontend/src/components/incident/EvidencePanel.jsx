import { useState } from 'react'
import { FileText, ChevronDown, Copy } from 'lucide-react'
import { formatTimestamp } from '../../utils/formatters'

export default function EvidencePanel({ evidence }) {
  const [expandedId, setExpandedId] = useState(null)

  if (!evidence || evidence.length === 0) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <div className="inline-flex h-10 w-10 items-center justify-center rounded-full mb-3" style={{ background: 'var(--bg-input)', color: 'var(--text-muted)' }}>
          <FileText size={18} />
        </div>
        <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>No diagnostic artifacts collected.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Evidence</span>
        <span className="px-2 py-0.5 rounded-full" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)' }}>{evidence.length}</span>
      </div>

      {evidence.map((e) => (
        <div key={e.id} className="glass rounded-lg overflow-hidden">
          <button
            onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
            className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors"
            style={{ background: 'transparent' }}
          >
            <div className="flex items-center gap-3">
              <div className="h-6 w-6 rounded-md flex items-center justify-center" style={{ background: 'var(--bg-input)', color: 'var(--text-muted)' }}>
                <FileText size={13} />
              </div>
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{e.tool_name}</span>
            </div>
            <div className="flex items-center gap-2">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{formatTimestamp(e.timestamp)}</span>
              <ChevronDown size={14} style={{ color: 'var(--text-muted)', transform: expandedId === e.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
            </div>
          </button>

          {expandedId === e.id && (
            <div style={{ borderTop: '1px solid var(--border)' }}>
              <div className="p-4" style={{ background: 'var(--terminal-bg)' }}>
                <div className="flex justify-between items-center mb-2">
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Raw Output</span>
                  <button
                    onClick={() => navigator.clipboard.writeText(e.raw_output)}
                    className="flex items-center gap-1 transition-colors"
                    style={{ fontSize: 11, fontWeight: 600, color: '#818cf8' }}
                  >
                    <Copy size={11} /> Copy
                  </button>
                </div>
                <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--terminal-text)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6, maxHeight: 256, overflow: 'auto' }}>
                  {e.raw_output}
                </pre>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
