import { useState } from 'react'
import { FileText, ChevronDown, Copy } from 'lucide-react'
import { formatTimestamp } from '../../utils/formatters'

// Helper to get a preview of the evidence (first meaningful line only)
function getEvidencePreview(rawOutput, maxChars = 80) {
  if (!rawOutput) return 'No output available'
  const lines = rawOutput.split('\n').filter(l => l.trim() && !l.startsWith('===') && !l.startsWith('---'))
  const firstLine = lines[0] || rawOutput.split('\n')[0] || ''
  if (firstLine.length <= maxChars) return firstLine
  return firstLine.substring(0, maxChars - 3) + '...'
}

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
    <div className="space-y-3" style={{ width: '100%', boxSizing: 'border-box' }}>
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Evidence</span>
        <span className="px-2 py-0.5 rounded-full" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)' }}>{evidence.length}</span>
      </div>

      {evidence.map((e) => (
        <div key={e.id} className="glass rounded-lg overflow-hidden" style={{ width: '100%', boxSizing: 'border-box' }}>
          <button
            onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
            className="flex items-center px-4 py-3 text-left transition-colors"
            style={{ 
              background: 'transparent', 
              width: '100%',
              boxSizing: 'border-box',
              overflow: 'hidden',
              gap: '12px'
            }}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
          >
            <div className="h-6 w-6 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'var(--bg-input)', color: 'var(--text-muted)', flexShrink: 0 }}>
              <FileText size={13} />
            </div>
            <div style={{ 
              flex: '1 1 0%', 
              minWidth: 0, 
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              width: 0  // Force flex item to respect minWidth: 0
            }}>
              <div style={{ 
                fontSize: 14, 
                fontWeight: 500, 
                color: 'var(--text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>{e.tool_name}</div>
              {!expandedId || expandedId !== e.id ? (
                <div style={{ 
                  fontFamily: 'var(--font-mono)', 
                  fontSize: 10, 
                  color: 'var(--text-muted)', 
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  lineHeight: 1.4
                }}>
                  {getEvidencePreview(e.raw_output, 250)}
                </div>
              ) : null}
            </div>
            <div style={{ 
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              flexShrink: 0,
              marginLeft: '8px'
            }}>
              <span style={{ 
                fontFamily: 'var(--font-mono)', 
                fontSize: 10, 
                color: 'var(--text-muted)', 
                whiteSpace: 'nowrap'
              }}>{formatTimestamp(e.timestamp).split(',')[0]}</span>
              <ChevronDown size={14} style={{ color: 'var(--text-muted)', transform: expandedId === e.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }} />
            </div>
          </button>

          {expandedId === e.id && (
            <div style={{ borderTop: '1px solid var(--border)' }}>
              <div className="p-4" style={{ background: 'var(--terminal-bg)' }}>
                <div className="flex justify-between items-center mb-3">
                  <div className="flex items-center gap-2">
                    <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Raw Output</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', padding: '2px 6px', borderRadius: 4, background: 'var(--bg-input)' }}>
                      {e.raw_output?.length.toLocaleString() || 0} chars
                    </span>
                  </div>
                  <button
                    onClick={(ev) => {
                      ev.stopPropagation()
                      navigator.clipboard.writeText(e.raw_output)
                    }}
                    className="flex items-center gap-1 px-2 py-1 rounded transition-colors"
                    style={{ fontSize: 11, fontWeight: 600, color: '#818cf8', background: 'var(--bg-input)' }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Copy size={11} /> Copy
                  </button>
                </div>
                <div className="relative rounded" style={{ 
                  maxHeight: '600px', 
                  overflow: 'auto',
                  background: 'var(--bg-input)',
                  padding: '12px',
                  border: '1px solid var(--border)'
                }}>
                  <pre style={{ 
                    fontFamily: 'var(--font-mono)', 
                    fontSize: 11, 
                    color: 'var(--terminal-text)', 
                    whiteSpace: 'pre-wrap', 
                    wordBreak: 'break-word', 
                    lineHeight: 1.5,
                    margin: 0,
                    padding: 0
                  }}>
                    {e.raw_output}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
