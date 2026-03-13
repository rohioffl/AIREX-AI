import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Link2, X, Plus, Search, ChevronRight } from 'lucide-react'
import { fetchRelatedIncidents, linkIncident, unlinkIncident, fetchIncidents } from '../../services/api'
import { formatRelativeTime } from '../../utils/formatters'
import { extractErrorMessage } from '../../utils/errorHandler'
import { useToasts } from '../../context/ToastContext'
import StateBadge from '../common/StateBadge'
import SeverityBadge from '../common/SeverityBadge'

export default function RelatedIncidentsPanel({ incident }) {
  const { addToast } = useToasts()
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [relationshipType, setRelationshipType] = useState('related')
  const [linkNote, setLinkNote] = useState('')

  useEffect(() => {
    loadRelated()
  }, [incident?.id])

  const loadRelated = async () => {
    if (!incident?.id) return
    try {
      setLoading(true)
      const data = await fetchRelatedIncidents(incident.id)
      setRelated(data)
    } catch (err) {
      console.error('Failed to load related incidents:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }
    try {
      setSearching(true)
      const data = await fetchIncidents({ search: searchQuery.trim(), limit: 10 })
      // Filter out current incident and already linked incidents
      const linkedIds = new Set(related.map(r => r.related_incident_id))
      const filtered = (data.items || []).filter(
        i => i.id !== incident.id && !linkedIds.has(i.id)
      )
      setSearchResults(filtered)
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to search incidents',
        severity: 'CRITICAL',
      })
    } finally {
      setSearching(false)
    }
  }

  const handleLink = async (relatedIncidentId) => {
    try {
      await linkIncident(incident.id, relatedIncidentId, relationshipType, linkNote || null)
      addToast({
        title: 'Success',
        message: 'Incidents linked successfully',
        severity: 'LOW',
      })
      setShowLinkModal(false)
      setSearchQuery('')
      setSearchResults([])
      setLinkNote('')
      setRelationshipType('related')
      loadRelated()
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to link incidents',
        severity: 'CRITICAL',
      })
    }
  }

  const handleUnlink = async (relatedIncidentId) => {
    if (!confirm('Are you sure you want to unlink these incidents?')) return
    try {
      await unlinkIncident(incident.id, relatedIncidentId)
      addToast({
        title: 'Success',
        message: 'Incidents unlinked successfully',
        severity: 'LOW',
      })
      loadRelated()
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to unlink incidents',
        severity: 'CRITICAL',
      })
    }
  }

  if (loading) {
    return (
      <div className="glass rounded-xl p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-elevated rounded w-1/3"></div>
          <div className="h-20 bg-elevated rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="glass rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 size={16} className="text-indigo-400" />
          <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-heading)' }}>
            Related Incidents
          </h3>
          {related.length > 0 && (
            <span className="px-2 py-0.5 rounded text-xs font-semibold" style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}>
              {related.length}
            </span>
          )}
        </div>
        <button
          onClick={() => setShowLinkModal(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors touch-manipulation"
          style={{ fontSize: 12, fontWeight: 600, background: 'rgba(99,102,241,0.1)', color: '#818cf8', minHeight: 36 }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(99,102,241,0.15)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(99,102,241,0.1)'}
        >
          <Plus size={14} />
          Link Incident
        </button>
      </div>

      {related.length === 0 ? (
        <div className="text-center py-8 text-muted">
          <p style={{ fontSize: 13 }}>No related incidents</p>
          <p style={{ fontSize: 12, marginTop: 4 }}>Link incidents to track relationships</p>
        </div>
      ) : (
        <div className="space-y-2">
          {related.map((rel) => (
            <div
              key={rel.related_incident_id}
              className="flex items-center justify-between gap-3 p-3 rounded-lg transition-colors"
              style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
            >
              <Link
                to={`/incidents/${rel.related_incident_id}`}
                className="flex-1 min-w-0 flex items-center gap-3"
                style={{ textDecoration: 'none', color: 'var(--text-primary)' }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <SeverityBadge severity={rel.related_incident.severity} />
                    <StateBadge state={rel.related_incident.state} />
                    {rel.relationship_type !== 'related' && (
                      <span className="px-1.5 py-0.5 rounded text-xs font-semibold" style={{ background: 'rgba(168,85,247,0.15)', color: '#c084fc' }}>
                        {rel.relationship_type}
                      </span>
                    )}
                  </div>
                  <div className="truncate font-medium" style={{ fontSize: 13 }}>
                    {rel.related_incident.title}
                  </div>
                  <div className="flex items-center gap-3 mt-1" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                    <span>{rel.related_incident.alert_type}</span>
                    <span>&middot;</span>
                    <span>{formatRelativeTime(rel.related_incident.created_at)}</span>
                  </div>
                  {rel.note && (
                    <div className="mt-1 text-xs text-muted italic">
                      Note: {rel.note}
                    </div>
                  )}
                </div>
                <ChevronRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              </Link>
              <button
                onClick={(e) => {
                  e.preventDefault()
                  handleUnlink(rel.related_incident_id)
                }}
                className="p-1.5 rounded hover:bg-elevated transition-colors touch-manipulation"
                style={{ minWidth: 32, minHeight: 32 }}
                title="Unlink"
              >
                <X size={14} style={{ color: 'var(--text-muted)' }} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Link Modal */}
      {showLinkModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowLinkModal(false)}>
          <div
            className="glass rounded-xl p-6 w-full max-w-md shadow-2xl border border-border"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="flex items-center gap-2 mb-4" style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-heading)' }}>
              <Link2 size={16} style={{ color: '#6366f1' }} />
              Link Incident
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Search Incident</label>
                <div className="flex gap-2">
                  <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                    <Search size={16} style={{ color: 'var(--text-muted)' }} />
                    <input
                      type="text"
                      placeholder="Search by title or ID..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      className="flex-1 bg-transparent border-none outline-none"
                      style={{ color: 'var(--text-primary)', fontSize: 13 }}
                    />
                  </div>
                  <button
                    onClick={handleSearch}
                    disabled={searching}
                    className="px-4 py-2 rounded-lg transition-colors touch-manipulation"
                    style={{ background: '#6366f1', color: '#fff', fontSize: 13, fontWeight: 600, minHeight: 40 }}
                  >
                    {searching ? '...' : 'Search'}
                  </button>
                </div>
              </div>

              {searchResults.length > 0 && (
                <div className="max-h-48 overflow-y-auto space-y-2">
                  {searchResults.map((inc) => (
                    <div
                      key={inc.id}
                      className="p-3 rounded-lg cursor-pointer transition-colors"
                      style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}
                      onClick={() => handleLink(inc.id)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(99,102,241,0.1)'
                        e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'var(--bg-input)'
                        e.currentTarget.style.borderColor = 'var(--border)'
                      }}
                    >
                      <div className="font-medium text-sm">{inc.title}</div>
                      <div className="flex items-center gap-2 mt-1" style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                        <span>{inc.alert_type}</span>
                        <span>&middot;</span>
                        <span>{inc.id.substring(0, 8)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium mb-2">Relationship Type</label>
                <select
                  value={relationshipType}
                  onChange={(e) => setRelationshipType(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-input text-text-primary"
                  style={{ fontSize: 13 }}
                >
                  <option value="related">Related</option>
                  <option value="parent">Parent</option>
                  <option value="child">Child</option>
                  <option value="duplicate">Duplicate</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Note (optional)</label>
                <textarea
                  value={linkNote}
                  onChange={(e) => setLinkNote(e.target.value)}
                  placeholder="Why are these incidents related?"
                  className="w-full px-3 py-2 rounded-lg border border-border bg-input text-text-primary"
                  style={{ fontSize: 13, minHeight: 80 }}
                  rows={3}
                />
              </div>

              <div className="flex gap-2 justify-end pt-4" style={{ borderTop: '1px solid var(--border)' }}>
                <button
                  onClick={() => {
                    setShowLinkModal(false)
                    setSearchQuery('')
                    setSearchResults([])
                    setLinkNote('')
                    setRelationshipType('related')
                  }}
                  className="px-4 py-2 rounded-lg transition-colors hover:bg-elevated touch-manipulation"
                  style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', minHeight: 40 }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
