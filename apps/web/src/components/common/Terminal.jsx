import { useState } from 'react'
import { Terminal as TerminalIcon, CheckCircle, Copy } from 'lucide-react'

export default function Terminal({ content, hostname = 'prod-web-01', maxHeight = 280 }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = (e) => {
    e.stopPropagation()
    navigator.clipboard.writeText(content || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="terminal">
      <div className="terminal-bar">
        <div className="terminal-dots">
          <span className="terminal-dot terminal-dot-red" />
          <span className="terminal-dot terminal-dot-yellow" />
          <span className="terminal-dot terminal-dot-green" />
        </div>
        <div className="terminal-title">
          <TerminalIcon size={12} />
          {hostname} — ssh
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center justify-center p-1 rounded transition-colors"
          style={{ color: 'var(--text-muted)' }}
          title="Copy output"
        >
          {copied ? <CheckCircle size={12} style={{ color: 'var(--color-accent-green)' }} /> : <Copy size={12} />}
        </button>
      </div>
      <div className="terminal-body" style={{ maxHeight }}>
        {content || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Waiting for diagnostics...</span>}
        <span className="terminal-cursor" />
      </div>
    </div>
  )
}
