import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTheme } from '../../context/ThemeContext'
import {
  GitBranch,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Server,
  AlertTriangle,
  Clock,
} from 'lucide-react'
import StateBadge from '../common/StateBadge'
import SeverityBadge from '../common/SeverityBadge'
import { formatRelativeTime } from '../../utils/formatters'

export default function CorrelationGroup({ incident }) {
  const { isDark } = useTheme()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)

  const correlatedIncidents = incident?.correlated_incidents || []
  const summary = incident?.correlation_summary || null
  const groupId = incident?.correlation_group_id || null

  if (!groupId || correlatedIncidents.length === 0) {
    return null
  }

  const totalIncidents = summary?.incident_count || correlatedIncidents.length + 1
  const affectedHosts = summary?.affected_hosts || 0

  return (
    <div
      className="glass rounded-xl overflow-hidden transition-all"
      style={{
        borderLeft: '3px solid rgba(168,85,247,0.5)',
        background: isDark ? 'rgba(168,85,247,0.03)' : '#FAF5FF',
        border: isDark ? undefined : '1px solid #E9D5FF',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left transition-colors"
        style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
        aria-label="Toggle correlation group"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <GitBranch size={14} style={{ color: 'var(--neon-purple)' }} />
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}
          >
            Cross-Host Correlation
          </span>
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: 'var(--neon-purple)',
              background: 'rgba(168,85,247,0.12)',
              border: '1px solid rgba(168,85,247,0.3)',
            }}
          >
            <AlertTriangle size={10} />
            {totalIncidents} incidents across {affectedHosts} hosts
          </span>
          {summary?.span_seconds > 0 && (
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: 'var(--text-muted)',
                background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                border: isDark
                  ? '1px solid rgba(255,255,255,0.08)'
                  : '1px solid rgba(0,0,0,0.06)',
              }}
            >
              <Clock size={10} />
              {summary.span_seconds < 60
                ? `${summary.span_seconds}s span`
                : `${Math.round(summary.span_seconds / 60)}m span`}
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
        <div className="px-4 pb-4 space-y-3">
          {/* Host summary */}
          {summary?.host_keys?.length > 0 && (
            <div
              className="flex items-center gap-2 flex-wrap p-2 rounded-lg"
              style={{
                fontSize: 11,
                background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                border: isDark
                  ? '1px solid rgba(255,255,255,0.06)'
                  : '1px solid rgba(0,0,0,0.06)',
              }}
            >
              <Server size={12} style={{ color: 'var(--text-muted)' }} />
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>
                Affected hosts:
              </span>
              {summary.host_keys.map((host) => (
                <span
                  key={host}
                  className="px-1.5 py-0.5 rounded"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    fontWeight: 600,
                    color: 'var(--neon-purple)',
                    background: 'var(--glow-purple)',
                    border: '1px solid rgba(168,85,247,0.2)',
                  }}
                >
                  {host}
                </span>
              ))}
            </div>
          )}

          {/* Correlated incident list */}
          <ul className="space-y-2">
            {correlatedIncidents.map((rel) => (
              <li key={rel.id}>
                <div
                  onClick={() => navigate(`/incidents/${rel.id}`)}
                  className="flex items-center justify-between gap-2 py-2 px-3 rounded-lg transition-colors cursor-pointer"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') navigate(`/incidents/${rel.id}`)
                  }}
                  style={{
                    background: isDark ? 'var(--bg-input)' : '#FFFFFF',
                    border: isDark
                      ? '1px solid var(--border)'
                      : '1px solid #E5E7EB',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = isDark
                      ? 'rgba(168,85,247,0.08)'
                      : '#F5F3FF'
                    e.currentTarget.style.borderColor = isDark
                      ? 'rgba(168,85,247,0.3)'
                      : '#C4B5FD'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isDark
                      ? 'var(--bg-input)'
                      : '#FFFFFF'
                    e.currentTarget.style.borderColor = isDark
                      ? 'var(--border)'
                      : '#E5E7EB'
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <div
                      className="truncate"
                      style={{ fontSize: 13, fontWeight: 500 }}
                    >
                      {rel.title}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      {rel.host_key && (
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: 10,
                            color: 'var(--neon-purple)',
                          }}
                        >
                          {rel.host_key}
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: 10,
                          color: 'var(--text-muted)',
                        }}
                      >
                        {formatRelativeTime(rel.created_at)}
                      </span>
                    </div>
                  </div>
                  <span className="flex items-center gap-2 flex-shrink-0">
                    <SeverityBadge severity={rel.severity} />
                    <StateBadge state={rel.state} />
                    <ChevronRight
                      size={14}
                      style={{ color: 'var(--neon-purple)' }}
                    />
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
