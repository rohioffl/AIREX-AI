import { useState, useEffect } from 'react'
import { X, Plus, FileText } from 'lucide-react'
import { fetchTemplates, createIncident } from '../../services/api'
import { useNavigate } from 'react-router-dom'

export default function CreateIncidentModal({ onClose, onSuccess }) {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    severity: 'MEDIUM',
    alert_type: '',
    host_key: '',
    meta: null,
  })

  useEffect(() => {
    // Load active templates
    fetchTemplates(true)
      .then(setTemplates)
      .catch(err => console.error('Failed to load templates:', err))
  }, [])

  useEffect(() => {
    // Apply template when selected
    if (selectedTemplate) {
      const template = templates.find(t => t.id === selectedTemplate)
      if (template) {
        setFormData(prev => ({
          ...prev,
          title: prev.title || template.default_title || '',
          severity: prev.severity || template.severity,
          alert_type: prev.alert_type || template.alert_type,
          meta: prev.meta || template.default_meta,
        }))
      }
    }
  }, [selectedTemplate, templates])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.title || !formData.alert_type) {
      alert('Title and Alert Type are required')
      return
    }

    setLoading(true)
    try {
      const data = {
        title: formData.title,
        description: formData.description || null,
        severity: formData.severity,
        alert_type: formData.alert_type,
        host_key: formData.host_key || null,
        meta: formData.meta || null,
      }

      const result = await createIncident(data, selectedTemplate)
      
      if (onSuccess) {
        onSuccess(result)
      } else {
        // Navigate to the new incident
        navigate(`/incidents/${result.incident_id}`)
      }
      onClose()
    } catch (error) {
      console.error('Failed to create incident:', error)
      alert(error.response?.data?.detail || 'Failed to create incident')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="glass rounded-xl p-6 w-full max-w-2xl shadow-2xl border border-border max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="flex items-center gap-2" style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>
            <Plus size={18} style={{ color: 'var(--neon-green)' }} />
            Create Incident
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-input transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Template Selection */}
          {templates.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-1">Template (Optional)</label>
              <select
                value={selectedTemplate || ''}
                onChange={(e) => setSelectedTemplate(e.target.value || null)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
              >
                <option value="">None - Create from scratch</option>
                {templates.map(template => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.alert_type} - {template.severity})
                  </option>
                ))}
              </select>
              {selectedTemplate && (
                <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                  Template will pre-fill fields below. You can still edit them.
                </p>
              )}
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium mb-1">Title *</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13 }}
              placeholder="e.g., High CPU usage on web-server-01"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13, minHeight: 100 }}
              rows={4}
              placeholder="Additional details about the incident..."
            />
          </div>

          {/* Severity and Alert Type */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Severity *</label>
              <select
                required
                value={formData.severity}
                onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
              >
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Alert Type *</label>
              <input
                type="text"
                required
                value={formData.alert_type}
                onChange={(e) => setFormData({ ...formData, alert_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input"
                style={{ fontSize: 13 }}
                placeholder="e.g., cpu_high, memory_high"
              />
            </div>
          </div>

          {/* Host Key */}
          <div>
            <label className="block text-sm font-medium mb-1">Host Key (Optional)</label>
            <input
              type="text"
              value={formData.host_key}
              onChange={(e) => setFormData({ ...formData, host_key: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              style={{ fontSize: 13 }}
              placeholder="e.g., web-server-01, 192.168.1.100"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-border hover:bg-input transition-colors"
              style={{ fontSize: 13 }}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg text-white transition-colors"
              style={{ 
                fontSize: 13,
                background: loading ? 'var(--text-muted)' : 'var(--neon-green)',
                cursor: loading ? 'not-allowed' : 'pointer'
              }}
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Incident'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
