import { useState } from 'react'
import { FileText, ChevronDown, Copy, Terminal, Check } from 'lucide-react'
import { motion as Motion, AnimatePresence } from 'framer-motion'
import { formatTimestamp } from '../../utils/formatters'
import AnomalyBadge from './AnomalyBadge'

// Helper to get a preview of the evidence (first meaningful line only)
function getEvidencePreview(rawOutput, maxChars = 80) {
  if (!rawOutput) return 'No output available'
  const lines = rawOutput.split('\n').filter(l => l.trim() && !l.startsWith('===') && !l.startsWith('---'))
  const firstLine = lines[0] || rawOutput.split('\n')[0] || ''
  if (firstLine.length <= maxChars) return firstLine
  return firstLine.substring(0, maxChars - 3) + '...'
}

// Extract commands executed from incident meta (investigation_run or openclaw_run)
function getCommandsExecuted(incident) {
  const meta = incident?.meta
  if (!meta) return []
  const run = meta.investigation_run || meta.openclaw_run
  if (!run) return []
  return run.commands_executed || []
}

// Command plate: shows shell commands executed on the target machine
function CommandPlate({ commands }) {
  const [copiedIdx, setCopiedIdx] = useState(null)

  if (!commands || commands.length === 0) return null

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 1500)
  }

  return (
    <div className="glass rounded-xl overflow-hidden mb-4">
      <div className="flex items-center gap-2 px-4 py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
        <Terminal size={13} style={{ color: 'var(--neon-green, #22c55e)' }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Commands Executed
        </span>
        <span className="px-2 py-0.5 rounded-full" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)' }}>
          {commands.length}
        </span>
      </div>
      <div style={{ background: 'var(--terminal-bg)', padding: '8px 0' }}>
        {commands.map((cmd, idx) => {
          const cmdText = cmd.command || cmd.name || String(cmd)
          const status = cmd.status || 'ok'
          const isCopied = copiedIdx === idx

          return (
            <div
              key={idx}
              className="flex items-center gap-3 px-4 py-1.5 group"
              style={{ minHeight: 28 }}
              onMouseEnter={(ev) => ev.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
              onMouseLeave={(ev) => ev.currentTarget.style.background = 'transparent'}
            >
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--neon-green, #22c55e)',
                flexShrink: 0,
                userSelect: 'none'
              }}>$</span>
              <code style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--terminal-text)',
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                lineHeight: 1.5
              }}>
                {cmdText}
              </code>
              {status && status !== 'ok' && (
                <span style={{
                  fontSize: 9,
                  fontWeight: 600,
                  color: 'var(--color-accent-red, #ef4444)',
                  flexShrink: 0,
                  padding: '1px 5px',
                  borderRadius: 3,
                  background: 'rgba(239,68,68,0.08)'
                }}>
                  {status}
                </span>
              )}
              <button
                onClick={() => handleCopy(cmdText, idx)}
                className="cmd-copy-btn"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 2,
                  color: isCopied ? 'var(--neon-green, #22c55e)' : 'var(--text-muted)',
                  opacity: isCopied ? 1 : 0.3,
                  transition: 'opacity 0.15s'
                }}
                onMouseEnter={(ev) => ev.currentTarget.style.opacity = '1'}
                onMouseLeave={(ev) => { if (copiedIdx !== idx) ev.currentTarget.style.opacity = '0.3' }}
              >
                {isCopied ? <Check size={12} /> : <Copy size={12} />}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Look up anomalies for a given tool_name from probe_results
function getAnomaliesForTool(incident, toolName) {
  if (!incident?.meta?.probe_results || !toolName) return null
  const probe = incident.meta.probe_results.find(
    (p) => p.tool_name === toolName
  )
  if (!probe || !probe.anomalies || probe.anomalies.length === 0) return null
  return probe.anomalies
}

export default function EvidencePanel({ evidence, incident }) {
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

  const commandsExecuted = getCommandsExecuted(incident)

  return (
    <div className="space-y-3" style={{ width: '100%', boxSizing: 'border-box' }}>
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Evidence</span>
        <span className="px-2 py-0.5 rounded-full" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-input)' }}>{evidence.length}</span>
      </div>

      <CommandPlate commands={commandsExecuted} />

      {evidence.map((e) => {
        const anomalies = getAnomaliesForTool(incident, e.tool_name)
        const isExpanded = expandedId === e.id

        return (
          <div key={e.id} className="glass rounded-lg overflow-hidden" style={{ width: '100%', boxSizing: 'border-box' }}>
            <button
              onClick={() => setExpandedId(isExpanded ? null : e.id)}
              className="flex items-center px-4 py-3 text-left transition-colors"
              style={{
                background: 'transparent',
                width: '100%',
                boxSizing: 'border-box',
                overflow: 'hidden',
                gap: '12px'
              }}
              onMouseEnter={(ev) => ev.currentTarget.style.opacity = '0.9'}
              onMouseLeave={(ev) => ev.currentTarget.style.opacity = '1'}
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
                width: 0
              }}>
                <div className="flex items-center gap-2">
                  <div style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: 'var(--text-primary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>{e.tool_name}</div>
                  {/* Collapsed anomaly count badge */}
                  {anomalies && !isExpanded && (
                    <span
                      className="inline-flex items-center rounded-full px-1.5 py-0.5"
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        flexShrink: 0,
                        color: anomalies.some(a => a.severity === 'critical') ? 'var(--color-accent-red)' : 'var(--color-accent-amber)',
                        background: anomalies.some(a => a.severity === 'critical') ? 'rgba(244,63,94,0.08)' : 'rgba(245,158,11,0.08)',
                        border: `1px solid ${anomalies.some(a => a.severity === 'critical') ? 'rgba(244,63,94,0.25)' : 'rgba(245,158,11,0.25)'}`,
                      }}
                    >
                      {anomalies.length} anomal{anomalies.length === 1 ? 'y' : 'ies'}
                    </span>
                  )}
                </div>
                {!isExpanded && (
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
                )}
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
                <ChevronDown size={14} style={{ color: 'var(--text-muted)', transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }} />
              </div>
            </button>

            <AnimatePresence initial={false}>
              {isExpanded && (
                <Motion.div
                  key="expanded"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease: 'easeInOut' }}
                  style={{ overflow: 'hidden', borderTop: '1px solid var(--border)' }}
                >
                  {/* Anomaly badges in expanded view */}
                  {anomalies && (
                    <div className="px-4 pt-3">
                      <AnomalyBadge anomalies={anomalies} />
                    </div>
                  )}
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
                        style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', background: 'var(--bg-input)' }}
                        onMouseEnter={(ev) => ev.currentTarget.style.opacity = '0.8'}
                        onMouseLeave={(ev) => ev.currentTarget.style.opacity = '1'}
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
                </Motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  )
}
