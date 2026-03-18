import { useState, useEffect, useRef } from 'react'
import { X, Plus } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { fetchTemplates, createIncident } from '../../services/api'
import { useNavigate } from 'react-router-dom'

const MotionDiv = motion.div
const MotionSpan = motion.span

export default function CreateIncidentModal({ onClose, onSuccess }) {
  const navigate = useNavigate()
  const modalRef = useRef(null)
  const previousFocusRef = useRef(null)
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    severity: 'MEDIUM',
    alert_type: '',
    host_key: '',
    meta: null,
  })

  // Focus management
  useEffect(() => {
    previousFocusRef.current = document.activeElement
    modalRef.current?.focus()
    return () => {
      previousFocusRef.current?.focus()
    }
  }, [])

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

  const validate = () => {
    const newErrors = {}
    if (!formData.title.trim()) {
      newErrors.title = 'Title is required'
    }
    if (!formData.alert_type.trim()) {
      newErrors.alert_type = 'Alert Type is required'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleFieldChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    // Clear field error on change
    if (errors[field]) {
      setErrors(prev => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
    setSubmitError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    setSubmitError(null)
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
        navigate(`/incidents/${result.incident_id}`)
      }
      onClose()
    } catch (error) {
      console.error('Failed to create incident:', error)
      setSubmitError(error.response?.data?.detail || 'Failed to create incident')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      ref={modalRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label="Create Incident"
      className="fixed inset-0 flex items-center justify-center z-50"
      onKeyDown={(e) => { if (e.key === 'Escape' && !loading) onClose() }}
    >
      <MotionDiv
        className="absolute inset-0"
        style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(6px)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={() => { if (!loading) onClose() }}
      />
      <MotionDiv
        className="glass rounded-xl p-6 w-full max-w-2xl shadow-2xl border border-border max-h-[90vh] overflow-y-auto relative"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="flex items-center gap-2" style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-heading)' }}>
            <Plus size={18} style={{ color: 'var(--neon-green)' }} />
            Create Incident
          </h2>
          <button
            onClick={onClose}
            disabled={loading}
            className="p-1 rounded-lg hover:bg-input transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={20} />
          </button>
        </div>

        {submitError && (
          <MotionDiv
            className="mb-4 p-3 rounded-lg text-sm"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#f87171' }}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {submitError}
          </MotionDiv>
        )}

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
              value={formData.title}
              onChange={(e) => handleFieldChange('title', e.target.value)}
              className="w-full px-3 py-2 rounded-lg border bg-input"
              style={{ 
                fontSize: 13,
                borderColor: errors.title ? '#f87171' : 'var(--border)',
              }}
              placeholder="e.g., High CPU usage on web-server-01"
            />
            <AnimatePresence>
              {errors.title && (
                <MotionSpan
                  className="text-xs mt-1 block"
                  style={{ color: '#f87171' }}
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                >
                  {errors.title}
                </MotionSpan>
              )}
            </AnimatePresence>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => handleFieldChange('description', e.target.value)}
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
                value={formData.severity}
                onChange={(e) => handleFieldChange('severity', e.target.value)}
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
                value={formData.alert_type}
                onChange={(e) => handleFieldChange('alert_type', e.target.value)}
                className="w-full px-3 py-2 rounded-lg border bg-input"
                style={{ 
                  fontSize: 13,
                  borderColor: errors.alert_type ? '#f87171' : 'var(--border)',
                }}
                placeholder="e.g., cpu_high, memory_high"
              />
              <AnimatePresence>
                {errors.alert_type && (
                  <MotionSpan
                    className="text-xs mt-1 block"
                    style={{ color: '#f87171' }}
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                  >
                    {errors.alert_type}
                  </MotionSpan>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Host Key */}
          <div>
            <label className="block text-sm font-medium mb-1">Host Key (Optional)</label>
            <input
              type="text"
              value={formData.host_key}
              onChange={(e) => handleFieldChange('host_key', e.target.value)}
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
              className="px-4 py-2 rounded-lg text-white transition-all hover:brightness-110 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ 
                fontSize: 13,
                background: loading ? 'var(--text-muted)' : 'var(--neon-green)',
              }}
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Incident'}
            </button>
          </div>
        </form>
      </MotionDiv>
    </div>
  )
}
