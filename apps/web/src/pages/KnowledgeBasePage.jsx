import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Search, Plus, Tag, Filter, X } from 'lucide-react'
import { fetchKnowledgeBase, createKnowledgeBaseEntry, updateKnowledgeBaseEntry, deleteKnowledgeBaseEntry } from '../services/api'
import { formatTimestamp } from '../utils/formatters'
import { extractErrorMessage } from '../utils/errorHandler'
import { useToasts } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'

export default function KnowledgeBasePage() {
  const { addToast } = useToasts()
  const { user } = useAuth()
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingEntry, setEditingEntry] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [alertTypeFilter, setAlertTypeFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')

  const loadEntries = useCallback(async () => {
    try {
      setLoading(true)
      const params = {}
      if (searchQuery) params.search = searchQuery
      if (alertTypeFilter !== 'all') params.alert_type = alertTypeFilter
      if (categoryFilter !== 'all') params.category = categoryFilter
      const data = await fetchKnowledgeBase(params)
      setEntries(data)
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to load knowledge base',
        severity: 'CRITICAL',
      })
    } finally {
      setLoading(false)
    }
  }, [searchQuery, alertTypeFilter, categoryFilter, addToast])

  useEffect(() => {
    loadEntries()
  }, [loadEntries])

  const handleCreate = async (formData) => {
    try {
      await createKnowledgeBaseEntry(formData)
      addToast({
        title: 'Success',
        message: 'Knowledge base entry created successfully',
        severity: 'LOW',
      })
      setShowCreateModal(false)
      loadEntries()
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to create entry',
        severity: 'CRITICAL',
      })
    }
  }

  const handleUpdate = async (entryId, formData) => {
    try {
      await updateKnowledgeBaseEntry(entryId, formData)
      addToast({
        title: 'Success',
        message: 'Knowledge base entry updated successfully',
        severity: 'LOW',
      })
      setEditingEntry(null)
      loadEntries()
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to update entry',
        severity: 'CRITICAL',
      })
    }
  }

  const handleDelete = async (entryId) => {
    if (!confirm('Are you sure you want to delete this knowledge base entry?')) return
    try {
      await deleteKnowledgeBaseEntry(entryId)
      addToast({
        title: 'Success',
        message: 'Knowledge base entry deleted successfully',
        severity: 'LOW',
      })
      loadEntries()
    } catch (err) {
      addToast({
        title: 'Error',
        message: extractErrorMessage(err) || 'Failed to delete entry',
        severity: 'CRITICAL',
      })
    }
  }

  const uniqueAlertTypes = [...new Set(entries.map(e => e.alert_type))].sort()
  const uniqueCategories = [...new Set(entries.map(e => e.category).filter(Boolean))].sort()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
            <BookOpen size={24} style={{ color: 'var(--text-muted)' }} />
            Knowledge Base
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Searchable repository of resolved incident summaries and solutions
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all touch-manipulation"
          style={{ fontSize: 13, fontWeight: 600, color: '#fff', background: 'var(--gradient-primary)', minHeight: 44 }}
        >
          <Plus size={16} />
          Add Entry
        </button>
      </div>

      {/* Search and Filters */}
      <div className="glass rounded-xl p-4 space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <Search size={16} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search knowledge base..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent border-none outline-none"
              style={{ color: 'var(--text-primary)', fontSize: 13 }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="p-1 rounded hover:bg-elevated transition-colors touch-manipulation"
                style={{ minWidth: 32, minHeight: 32 }}
              >
                <X size={14} style={{ color: 'var(--text-muted)' }} />
              </button>
            )}
          </div>

          <select
            value={alertTypeFilter}
            onChange={(e) => setAlertTypeFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-input text-text-primary touch-manipulation"
            style={{ fontSize: 13, minHeight: 44 }}
          >
            <option value="all">All Alert Types</option>
            {uniqueAlertTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border bg-input text-text-primary touch-manipulation"
            style={{ fontSize: 13, minHeight: 44 }}
          >
            <option value="all">All Categories</option>
            {uniqueCategories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Entries Grid */}
      {entries.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center">
          <BookOpen size={48} style={{ color: 'var(--text-muted)', margin: '0 auto 16px' }} />
          <p style={{ fontSize: 16, color: 'var(--text-heading)', marginBottom: 4 }}>No knowledge base entries</p>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Create entries to build a searchable knowledge base</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="glass rounded-xl p-5 hover-lift transition-all"
              style={{ border: '1px solid var(--border)' }}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="font-semibold text-heading flex-1" style={{ fontSize: 16 }}>
                  {entry.title}
                </h3>
                {user?.role === 'admin' && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setEditingEntry(entry)}
                      className="p-1.5 rounded hover:bg-elevated transition-colors touch-manipulation"
                      style={{ minWidth: 32, minHeight: 32 }}
                      title="Edit"
                    >
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--text-muted)' }}>
                        <path d="M8.5 2.5L11.5 5.5L4.5 12.5H1.5V9.5L8.5 2.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDelete(entry.id)}
                      className="p-1.5 rounded hover:bg-elevated transition-colors touch-manipulation"
                      style={{ minWidth: 32, minHeight: 32 }}
                      title="Delete"
                    >
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--color-accent-red)' }}>
                        <path d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>
                )}
              </div>

              <p className="text-sm text-secondary mb-3 line-clamp-3" style={{ fontSize: 13 }}>
                {entry.summary}
              </p>

              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="px-2 py-1 rounded text-xs font-semibold" style={{ background: 'var(--glow-indigo)', color: 'var(--neon-indigo)' }}>
                  {entry.alert_type}
                </span>
                {entry.category && (
                  <span className="px-2 py-1 rounded text-xs font-semibold" style={{ background: 'var(--glow-purple)', color: 'var(--neon-purple)' }}>
                    {entry.category}
                  </span>
                )}
                {entry.tags && entry.tags.length > 0 && (
                  <div className="flex items-center gap-1">
                    <Tag size={12} style={{ color: 'var(--text-muted)' }} />
                    {entry.tags.slice(0, 2).map(tag => (
                      <span key={tag} className="px-1.5 py-0.5 rounded text-xs" style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)' }}>
                        {tag}
                      </span>
                    ))}
                    {entry.tags.length > 2 && (
                      <span className="text-xs text-muted">+{entry.tags.length - 2}</span>
                    )}
                  </div>
                )}
              </div>

              {entry.root_cause && (
                <div className="mb-2">
                  <div className="text-xs font-semibold text-muted mb-1">Root Cause</div>
                  <p className="text-xs text-secondary line-clamp-2">{entry.root_cause}</p>
                </div>
              )}

              {entry.incident_id && (
                <Link
                  to={`/incidents/${entry.incident_id}`}
                  className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                  style={{ fontSize: 11 }}
                >
                  View related incident →
                </Link>
              )}

              <div className="mt-3 pt-3 border-t border-border">
                <div className="text-xs text-muted" style={{ fontFamily: 'var(--font-mono)' }}>
                  {formatTimestamp(entry.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {(showCreateModal || editingEntry) && (
        <KnowledgeBaseModal
          entry={editingEntry}
          onClose={() => {
            setShowCreateModal(false)
            setEditingEntry(null)
          }}
          onSave={editingEntry ? (data) => handleUpdate(editingEntry.id, data) : handleCreate}
        />
      )}
    </div>
  )
}

function KnowledgeBaseModal({ entry, onClose, onSave }) {
  const [formData, setFormData] = useState({
    incident_id: entry?.incident_id || null,
    title: entry?.title || '',
    summary: entry?.summary || '',
    root_cause: entry?.root_cause || '',
    resolution_steps: entry?.resolution_steps || '',
    alert_type: entry?.alert_type || '',
    category: entry?.category || '',
    tags: entry?.tags?.join(', ') || '',
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const data = {
      ...formData,
      tags: formData.tags ? formData.tags.split(',').map(t => t.trim()).filter(Boolean) : null,
      incident_id: formData.incident_id || null,
    }
    onSave(data)
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="glass rounded-xl p-6 w-full max-w-2xl shadow-2xl border border-border max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="flex items-center gap-2 mb-4" style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>
          <BookOpen size={18} style={{ color: 'var(--neon-indigo)' }} />
          {entry ? 'Edit Knowledge Base Entry' : 'Create Knowledge Base Entry'}
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title *</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13 }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Summary *</label>
            <textarea
              required
              value={formData.summary}
              onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13, minHeight: 100 }}
              rows={4}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Alert Type *</label>
              <input
                type="text"
                required
                value={formData.alert_type}
                onChange={(e) => setFormData({ ...formData, alert_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Category</label>
              <input
                type="text"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Root Cause</label>
            <textarea
              value={formData.root_cause}
              onChange={(e) => setFormData({ ...formData, root_cause: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13, minHeight: 80 }}
              rows={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Resolution Steps</label>
            <textarea
              value={formData.resolution_steps}
              onChange={(e) => setFormData({ ...formData, resolution_steps: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13, minHeight: 100 }}
              rows={4}
              placeholder="Step 1: ...&#10;Step 2: ..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
            <input
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13 }}
              placeholder="tag1, tag2, tag3"
            />
          </div>

          <div className="flex gap-2 justify-end pt-4" style={{ borderTop: '1px solid var(--border)' }}>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg transition-colors hover:bg-elevated touch-manipulation"
              style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', minHeight: 40 }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg transition-all touch-manipulation"
              style={{ fontSize: 13, fontWeight: 600, color: '#fff', background: 'var(--gradient-primary)', minHeight: 40 }}
            >
              {entry ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
