import { useState, useEffect, useCallback } from 'react'
import { Plus, Edit, Trash2, Copy, ChevronDown, ChevronUp, GripVertical, Play, Pause, AlertTriangle, Terminal, Globe, Bell, GitBranch } from 'lucide-react'
import { fetchRunbooks, createRunbook, updateRunbook, deleteRunbook, duplicateRunbook } from '../services/api'
import { useToast } from '../context/ToastContext'

const ACTION_TYPES = [
  { value: 'manual', label: 'Manual Step', icon: '📋', color: 'bg-gray-100 dark:bg-gray-700' },
  { value: 'command', label: 'Run Command', icon: '⌨️', color: 'bg-blue-100 dark:bg-blue-900/30' },
  { value: 'api_call', label: 'API Call', icon: '🌐', color: 'bg-green-100 dark:bg-green-900/30' },
  { value: 'notification', label: 'Send Notification', icon: '🔔', color: 'bg-yellow-100 dark:bg-yellow-900/30' },
  { value: 'condition', label: 'Condition Check', icon: '🔀', color: 'bg-purple-100 dark:bg-purple-900/30' },
]

const ON_FAILURE_OPTIONS = [
  { value: 'continue', label: 'Continue' },
  { value: 'stop', label: 'Stop Execution' },
  { value: 'skip_to', label: 'Skip To Step' },
]

function StepEditor({ step, index, onUpdate, onRemove, onMoveUp, onMoveDown, isFirst, isLast }) {
  const [expanded, setExpanded] = useState(true)
  const actionType = ACTION_TYPES.find(a => a.value === step.action_type) || ACTION_TYPES[0]

  return (
    <div className={`border rounded-lg ${actionType.color} border-gray-200 dark:border-gray-600`}>
      <div className="flex items-center gap-2 p-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <GripVertical className="w-4 h-4 text-gray-400 cursor-grab" />
        <span className="text-lg">{actionType.icon}</span>
        <span className="font-medium text-sm dark:text-white flex-1">
          Step {index + 1}: {step.title || 'Untitled'}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={(e) => { e.stopPropagation(); onMoveUp() }} disabled={isFirst}
            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-30">
            <ChevronUp className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onMoveDown() }} disabled={isLast}
            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-30">
            <ChevronDown className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onRemove() }}
            className="p-1 rounded hover:bg-red-200 dark:hover:bg-red-900/30 text-red-500">
            <Trash2 className="w-4 h-4" />
          </button>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </div>
      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              type="text" placeholder="Step title" value={step.title}
              onChange={(e) => onUpdate({ ...step, title: e.target.value })}
              className="px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm"
            />
            <select value={step.action_type} onChange={(e) => onUpdate({ ...step, action_type: e.target.value })}
              className="px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm">
              {ACTION_TYPES.map(a => <option key={a.value} value={a.value}>{a.icon} {a.label}</option>)}
            </select>
          </div>
          <textarea
            placeholder="Step description / instructions" value={step.description}
            onChange={(e) => onUpdate({ ...step, description: e.target.value })}
            className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm h-20"
          />
          {(step.action_type === 'command' || step.action_type === 'api_call') && (
            <div className="space-y-2">
              <input
                type="text"
                placeholder={step.action_type === 'command' ? 'Command to execute (e.g., systemctl restart nginx)' : 'API endpoint URL'}
                value={step.action_config?.command || step.action_config?.url || ''}
                onChange={(e) => onUpdate({ ...step, action_config: { ...step.action_config, [step.action_type === 'command' ? 'command' : 'url']: e.target.value } })}
                className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm font-mono"
              />
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Timeout (seconds)</label>
              <input type="number" value={step.timeout_seconds || ''} placeholder="No timeout"
                onChange={(e) => onUpdate({ ...step, timeout_seconds: e.target.value ? parseInt(e.target.value) : null })}
                className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">On Failure</label>
              <select value={step.on_failure} onChange={(e) => onUpdate({ ...step, on_failure: e.target.value })}
                className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white text-sm">
                {ON_FAILURE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RunbookEditor({ runbook, onSave, onCancel }) {
  const [form, setForm] = useState({
    name: runbook?.name || '',
    description: runbook?.description || '',
    alert_type: runbook?.alert_type || '',
    severity: runbook?.severity || '',
    is_active: runbook?.is_active ?? true,
    tags: (runbook?.tags || []).join(', '),
    steps: runbook?.steps || [],
  })

  const addStep = () => {
    setForm(f => ({
      ...f,
      steps: [...f.steps, { order: f.steps.length + 1, title: '', description: '', action_type: 'manual', action_config: {}, timeout_seconds: null, on_failure: 'continue' }]
    }))
  }

  const updateStep = (index, step) => {
    setForm(f => ({ ...f, steps: f.steps.map((s, i) => i === index ? step : s) }))
  }

  const removeStep = (index) => {
    setForm(f => ({ ...f, steps: f.steps.filter((_, i) => i !== index).map((s, i) => ({ ...s, order: i + 1 })) }))
  }

  const moveStep = (index, direction) => {
    setForm(f => {
      const steps = [...f.steps]
      const targetIndex = index + direction
      if (targetIndex < 0 || targetIndex >= steps.length) return f
      ;[steps[index], steps[targetIndex]] = [steps[targetIndex], steps[index]]
      return { ...f, steps: steps.map((s, i) => ({ ...s, order: i + 1 })) }
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave({
      ...form,
      tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium dark:text-gray-300 mb-1">Name *</label>
          <input type="text" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} required
            className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white" />
        </div>
        <div>
          <label className="block text-sm font-medium dark:text-gray-300 mb-1">Alert Type *</label>
          <input type="text" value={form.alert_type} onChange={(e) => setForm(f => ({ ...f, alert_type: e.target.value }))} required
            className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white" />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium dark:text-gray-300 mb-1">Description</label>
        <textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
          className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white h-20" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium dark:text-gray-300 mb-1">Severity</label>
          <select value={form.severity} onChange={(e) => setForm(f => ({ ...f, severity: e.target.value }))}
            className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white">
            <option value="">Any</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium dark:text-gray-300 mb-1">Tags</label>
          <input type="text" value={form.tags} onChange={(e) => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="tag1, tag2"
            className="w-full px-3 py-2 rounded border dark:bg-gray-800 dark:border-gray-600 dark:text-white" />
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))}
              className="w-4 h-4 rounded" />
            <span className="text-sm dark:text-gray-300">Active</span>
          </label>
        </div>
      </div>

      {/* Steps */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold dark:text-white">Steps ({form.steps.length})</h3>
          <button type="button" onClick={addStep}
            className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus className="w-4 h-4" /> Add Step
          </button>
        </div>
        <div className="space-y-2">
          {form.steps.map((step, idx) => (
            <StepEditor key={idx} step={step} index={idx}
              onUpdate={(s) => updateStep(idx, s)}
              onRemove={() => removeStep(idx)}
              onMoveUp={() => moveStep(idx, -1)}
              onMoveDown={() => moveStep(idx, 1)}
              isFirst={idx === 0} isLast={idx === form.steps.length - 1}
            />
          ))}
          {form.steps.length === 0 && (
            <div className="text-center py-8 text-gray-400 border-2 border-dashed rounded-lg dark:border-gray-600">
              No steps yet. Click "Add Step" to start building your runbook.
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-3 justify-end pt-4 border-t dark:border-gray-700">
        <button type="button" onClick={onCancel}
          className="px-4 py-2 border rounded-lg dark:border-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
          Cancel
        </button>
        <button type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          {runbook ? 'Update Runbook' : 'Create Runbook'}
        </button>
      </div>
    </form>
  )
}

export default function RunbooksPage() {
  const [runbooks, setRunbooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null) // null | 'new' | runbook object
  const [filterActive, setFilterActive] = useState(false)
  const { addToast } = useToast()

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchRunbooks(filterActive)
      setRunbooks(data.runbooks || [])
    } catch (err) {
      addToast('Failed to load runbooks', 'error')
    } finally {
      setLoading(false)
    }
  }, [filterActive])

  useEffect(() => { load() }, [load])

  const handleSave = async (data) => {
    try {
      if (editing && editing !== 'new') {
        await updateRunbook(editing.id, data)
        addToast('Runbook updated', 'success')
      } else {
        await createRunbook(data)
        addToast('Runbook created', 'success')
      }
      setEditing(null)
      load()
    } catch (err) {
      addToast('Failed to save runbook', 'error')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this runbook?')) return
    try {
      await deleteRunbook(id)
      addToast('Runbook deleted', 'success')
      load()
    } catch (err) {
      addToast('Failed to delete runbook', 'error')
    }
  }

  const handleDuplicate = async (id) => {
    try {
      await duplicateRunbook(id)
      addToast('Runbook duplicated', 'success')
      load()
    } catch (err) {
      addToast('Failed to duplicate runbook', 'error')
    }
  }

  if (editing) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold dark:text-white mb-6">
          {editing === 'new' ? 'Create Runbook' : `Edit: ${editing.name}`}
        </h1>
        <RunbookEditor
          runbook={editing === 'new' ? null : editing}
          onSave={handleSave}
          onCancel={() => setEditing(null)}
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold dark:text-white">Runbooks</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            Visual runbook editor for structured incident response procedures
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm dark:text-gray-300">
            <input type="checkbox" checked={filterActive} onChange={(e) => setFilterActive(e.target.checked)} className="rounded" />
            Active only
          </label>
          <button onClick={() => setEditing('new')}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Plus className="w-4 h-4" /> New Runbook
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : runbooks.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg">No runbooks yet</p>
          <p className="text-sm mt-1">Create your first runbook to automate incident response</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {runbooks.map(rb => (
            <div key={rb.id} className="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold dark:text-white">{rb.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${rb.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                      {rb.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 text-xs">
                      v{rb.version}
                    </span>
                  </div>
                  {rb.description && <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">{rb.description}</p>}
                  <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                    <span>Alert: <strong>{rb.alert_type}</strong></span>
                    {rb.severity && <span>Severity: <strong>{rb.severity}</strong></span>}
                    <span>{(rb.steps || []).length} steps</span>
                    {rb.tags && rb.tags.length > 0 && (
                      <div className="flex gap-1">
                        {rb.tags.map(tag => (
                          <span key={tag} className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">{tag}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setEditing(rb)} className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Edit">
                    <Edit className="w-4 h-4 text-gray-500" />
                  </button>
                  <button onClick={() => handleDuplicate(rb.id)} className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700" title="Duplicate">
                    <Copy className="w-4 h-4 text-gray-500" />
                  </button>
                  <button onClick={() => handleDelete(rb.id)} className="p-2 rounded hover:bg-red-100 dark:hover:bg-red-900/20" title="Delete">
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
              {/* Step preview */}
              {(rb.steps || []).length > 0 && (
                <div className="mt-3 pt-3 border-t dark:border-gray-700">
                  <div className="flex items-center gap-2 overflow-x-auto pb-1">
                    {(rb.steps || []).map((step, idx) => {
                      const at = ACTION_TYPES.find(a => a.value === step.action_type) || ACTION_TYPES[0]
                      return (
                        <div key={idx} className="flex items-center gap-1">
                          {idx > 0 && <span className="text-gray-300 dark:text-gray-600">→</span>}
                          <span className="whitespace-nowrap px-2 py-1 rounded text-xs bg-gray-100 dark:bg-gray-700 dark:text-gray-300">
                            {at.icon} {step.title || `Step ${idx + 1}`}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
