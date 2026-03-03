import { useState, useEffect } from 'react'
import { useTheme } from '../../context/ThemeContext'
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import { fetchAutoRunbook } from '../../services/api'
import { formatTimestamp } from '../../utils/formatters'

export default function AutoRunbook({ incident }) {
  const { isDark } = useTheme()
  const [expanded, setExpanded] = useState(false)
  const [runbook, setRunbook] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const meta = incident?.meta || {}
  const hasRunbook = Boolean(meta._auto_runbook_source_id)
  const generatedAt = meta._auto_runbook_generated_at || null

  // Only show for resolved incidents that have an auto-generated runbook
  if (!hasRunbook || incident?.state !== 'RESOLVED') {
    return null
  }

  const handleExpand = async () => {
    const willExpand = !expanded
    setExpanded(willExpand)

    if (willExpand && !runbook && !loading) {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAutoRunbook(incident.id)
        setRunbook(data)
      } catch (err) {
        setError(err?.response?.data?.detail || 'Failed to load runbook')
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <div
      className="glass rounded-xl overflow-hidden transition-all"
      style={{
        borderLeft: '3px solid rgba(16,185,129,0.5)',
        background: isDark ? 'rgba(16,185,129,0.03)' : '#ECFDF5',
        border: isDark ? undefined : '1px solid #A7F3D0',
      }}
    >
      {/* Header */}
      <button
        onClick={handleExpand}
        className="w-full flex items-center justify-between p-4 text-left transition-colors"
        style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
        aria-label="Toggle auto-generated runbook"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <BookOpen size={14} style={{ color: '#10b981' }} />
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}
          >
            Auto-Generated Runbook
          </span>
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: '#10b981',
              background: 'rgba(16,185,129,0.12)',
              border: '1px solid rgba(16,185,129,0.25)',
            }}
          >
            <FileText size={10} />
            Available
          </span>
          {generatedAt && (
            <span
              className="inline-flex items-center gap-1"
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <Clock size={10} />
              {formatTimestamp(generatedAt)}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} />
        ) : (
          <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-4 pb-4">
          {loading && (
            <div
              className="flex items-center gap-2 p-4 rounded-lg"
              style={{
                fontSize: 12,
                color: 'var(--text-muted)',
                background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
              }}
            >
              <Loader2 size={14} className="animate-spin" />
              Loading runbook...
            </div>
          )}

          {error && (
            <div
              className="flex items-center gap-2 p-3 rounded-lg"
              style={{
                fontSize: 12,
                color: '#f87171',
                background: 'rgba(248,113,113,0.08)',
                border: '1px solid rgba(248,113,113,0.2)',
              }}
            >
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {runbook && (
            <div
              className="rounded-lg p-4 overflow-auto"
              style={{
                background: isDark ? 'rgba(0,0,0,0.3)' : '#FFFFFF',
                border: isDark
                  ? '1px solid rgba(255,255,255,0.06)'
                  : '1px solid #D1FAE5',
                maxHeight: 600,
              }}
            >
              <div
                className="prose prose-sm max-w-none"
                style={{
                  fontSize: 13,
                  lineHeight: 1.7,
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {runbook.content}
              </div>
              {runbook.chunk_count > 0 && (
                <div
                  className="mt-3 pt-3 flex items-center gap-3"
                  style={{
                    borderTop: isDark
                      ? '1px solid rgba(255,255,255,0.06)'
                      : '1px solid #D1FAE5',
                    fontSize: 10,
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <span>{runbook.chunk_count} chunks indexed in RAG</span>
                  <span>|</span>
                  <span>Alert type: {runbook.alert_type}</span>
                  {runbook.resolution_type && (
                    <>
                      <span>|</span>
                      <span>Resolution: {runbook.resolution_type}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
