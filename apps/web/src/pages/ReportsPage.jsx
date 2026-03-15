import { useState, useEffect } from 'react'
import { Plus, FileText, Calendar, Trash2, Edit, Play } from 'lucide-react'
import { fetchReports, createReport, updateReport, deleteReport, generateReport } from '../services/api'
import { formatTimestamp } from '../utils/formatters'

export default function ReportsPage() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingReport, setEditingReport] = useState(null)
  const [generatingReportId, setGeneratingReportId] = useState(null)

  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    try {
      setLoading(true)
      const data = await fetchReports()
      setReports(data)
    } catch (error) {
      console.error('Failed to load reports:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (data) => {
    try {
      await createReport(data)
      await loadReports()
      setShowCreateModal(false)
    } catch (error) {
      console.error('Failed to create report:', error)
      alert(error.response?.data?.detail || 'Failed to create report')
    }
  }

  const handleUpdate = async (id, data) => {
    try {
      await updateReport(id, data)
      await loadReports()
      setEditingReport(null)
    } catch (error) {
      console.error('Failed to update report:', error)
      alert(error.response?.data?.detail || 'Failed to update report')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this report template?')) return
    try {
      await deleteReport(id)
      await loadReports()
    } catch (error) {
      console.error('Failed to delete report:', error)
      alert(error.response?.data?.detail || 'Failed to delete report')
    }
  }

  const handleGenerate = async (id) => {
    try {
      setGeneratingReportId(id)
      const result = await generateReport(id)
      // Download as JSON
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report-${id}-${new Date().toISOString()}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to generate report:', error)
      alert(error.response?.data?.detail || 'Failed to generate report')
    } finally {
      setGeneratingReportId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-muted">Loading reports...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-heading)' }}>
            Custom Reports
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Create and manage scheduled incident reports
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 rounded-lg text-white flex items-center gap-2 transition-colors"
          style={{ background: 'var(--neon-green)', fontSize: 13 }}
        >
          <Plus size={16} />
          Create Report
        </button>
      </div>

      {reports.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center">
          <FileText size={48} className="mx-auto mb-4" style={{ color: 'var(--text-muted)' }} />
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-heading)' }}>
            No Report Templates
          </h3>
          <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
            Create your first report template to start generating scheduled reports.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 rounded-lg text-white"
            style={{ background: 'var(--neon-green)', fontSize: 13 }}
          >
            Create Report Template
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reports.map((report) => (
            <div key={report.id} className="glass rounded-xl p-4 border border-border">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="font-semibold mb-1" style={{ color: 'var(--text-heading)' }}>
                    {report.name}
                  </h3>
                  {report.description && (
                    <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                      {report.description}
                    </p>
                  )}
                </div>
                <span
                  className={`px-2 py-1 rounded text-xs ${
                    report.is_active ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-500'
                  }`}
                >
                  {report.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              <div className="space-y-2 mb-4">
                <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <Calendar size={14} />
                  <span>{report.schedule_type.charAt(0).toUpperCase() + report.schedule_type.slice(1)}</span>
                </div>
                <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <FileText size={14} />
                  <span>{report.format.toUpperCase()}</span>
                </div>
                {report.recipients && report.recipients.length > 0 && (
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {report.recipients.length} recipient{report.recipients.length !== 1 ? 's' : ''}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 pt-3 border-t border-border">
                <button
                  onClick={() => handleGenerate(report.id)}
                  disabled={generatingReportId === report.id}
                  className="flex-1 px-3 py-1.5 rounded text-xs flex items-center justify-center gap-1 transition-colors"
                  style={{
                    background: generatingReportId === report.id ? 'var(--text-muted)' : 'var(--neon-indigo)',
                    color: 'white',
                    cursor: generatingReportId === report.id ? 'not-allowed' : 'pointer',
                  }}
                  title="Generate Report"
                >
                  <Play size={12} />
                  Generate
                </button>
                <button
                  onClick={() => setEditingReport(report)}
                  className="p-1.5 rounded hover:bg-input transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                  title="Edit"
                >
                  <Edit size={14} />
                </button>
                <button
                  onClick={() => handleDelete(report.id)}
                  className="p-1.5 rounded hover:bg-input transition-colors"
                  style={{ color: 'var(--color-accent-red)' }}
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              <div className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                Created {formatTimestamp(report.created_at)}
              </div>
            </div>
          ))}
        </div>
      )}

      {(showCreateModal || editingReport) && (
        <ReportModal
          report={editingReport}
          onClose={() => {
            setShowCreateModal(false)
            setEditingReport(null)
          }}
          onSave={editingReport ? (data) => handleUpdate(editingReport.id, data) : handleCreate}
        />
      )}
    </div>
  )
}

function ReportModal({ report, onClose, onSave }) {
  const [formData, setFormData] = useState({
    name: report?.name || '',
    description: report?.description || '',
    schedule_type: report?.schedule_type || 'manual',
    schedule_config: report?.schedule_config || null,
    filters: report?.filters || null,
    format: report?.format || 'json',
    recipients: report?.recipients?.join(', ') || '',
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const data = {
      ...formData,
      recipients: formData.recipients
        ? formData.recipients.split(',').map((r) => r.trim()).filter(Boolean)
        : null,
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
          <FileText size={18} style={{ color: 'var(--neon-indigo)' }} />
          {report ? 'Edit Report Template' : 'Create Report Template'}
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Name *</label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13 }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13, minHeight: 80 }}
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Schedule Type *</label>
              <select
                required
                value={formData.schedule_type}
                onChange={(e) => setFormData({ ...formData, schedule_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
              >
                <option value="manual">Manual</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Format *</label>
              <select
                required
                value={formData.format}
                onChange={(e) => setFormData({ ...formData, format: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
              >
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Recipients (comma-separated emails)</label>
            <input
              type="text"
              value={formData.recipients}
              onChange={(e) => setFormData({ ...formData, recipients: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13 }}
              placeholder="user1@example.com, user2@example.com"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-border hover:bg-input transition-colors"
              style={{ fontSize: 13 }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg text-white transition-colors"
              style={{ background: 'var(--neon-green)', fontSize: 13 }}
            >
              {report ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
