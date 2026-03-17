import { useState, useEffect, useCallback } from 'react'
import { Plus, Edit, Trash2, Copy, ChevronDown, ChevronUp, GripVertical, Play, Pause, AlertTriangle, Terminal, Globe, Bell, GitBranch, History, X } from 'lucide-react'
import { fetchRunbooks, createRunbook, updateRunbook, deleteRunbook, duplicateRunbook, fetchRunbookVersions } from '../services/api'
import { useToasts } from '../context/ToastContext'

const ACTION_TYPES = [
  { value: 'manual', label: 'Manual Step', icon: '📋', color: 'bg-elevated border-border' },
  { value: 'command', label: 'Run Command', icon: '⌨️', color: 'bg-blue-500/5 border-blue-500/20' },
  { value: 'api_call', label: 'API Call', icon: '🌐', color: 'bg-emerald-500/5 border-emerald-500/20' },
  { value: 'notification', label: 'Send Notification', icon: '🔔', color: 'bg-amber-500/5 border-amber-500/20' },
  { value: 'condition', label: 'Condition Check', icon: '🔀', color: 'bg-purple-500/5 border-purple-500/20' }
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
    <div className={`rounded-xl border ${actionType.color}`}>
      <div className="flex items-center gap-2 p-3 cursor-pointer hover:bg-elevated/50 transition-colors" onClick={() => setExpanded(!expanded)}>
        <GripVertical className="w-4 h-4 text-muted cursor-grab" />
        <span className="text-lg">{actionType.icon}</span>
        <span className="font-medium text-sm text-heading flex-1">
          Step {index + 1}: {step.title || 'Untitled'}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={(e) => { e.stopPropagation(); onMoveUp() }} disabled={isFirst}
            className="p-1 rounded-lg hover:bg-input transition-colors disabled:opacity-30 text-muted">
            <ChevronUp className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onMoveDown() }} disabled={isLast}
            className="p-1 rounded-lg hover:bg-input transition-colors disabled:opacity-30 text-muted">
            <ChevronDown className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onRemove() }}
            className="p-1 rounded-lg hover:bg-red-500/10 text-red-500 transition-colors">
            <Trash2 className="w-4 h-4" />
          </button>
          {expanded ? <ChevronUp className="w-4 h-4 text-muted ml-2" /> : <ChevronDown className="w-4 h-4 text-muted ml-2" />}
        </div>
      </div>
      {expanded && (
        <div className="p-4 space-y-4 border-t border-border bg-input/20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">Step Title</label>
              <input
                type="text" placeholder="Step title" value={step.title}
                onChange={(e) => onUpdate({ ...step, title: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input text-sm text-primary focus:border-primary outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">Action Type</label>
              <select value={step.action_type} onChange={(e) => onUpdate({ ...step, action_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input text-sm text-primary focus:border-primary outline-none transition-colors">
                {ACTION_TYPES.map(a => <option key={a.value} value={a.value}>{a.icon} {a.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary mb-1">Description / Instructions</label>
            <textarea
              placeholder="Step description / instructions" value={step.description}
              onChange={(e) => onUpdate({ ...step, description: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input text-sm text-primary focus:border-primary outline-none transition-colors h-20"
            />
          </div>
          {(step.action_type === 'command' || step.action_type === 'api_call') && (
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">{step.action_type === 'command' ? 'Command to execute' : 'API endpoint URL'}</label>
              <input
                type="text"
                placeholder={step.action_type === 'command' ? 'e.g., systemctl restart nginx' : 'https://api.example.com/webhook'}
                value={step.action_config?.command || step.action_config?.url || ''}
                onChange={(e) => onUpdate({ ...step, action_config: { ...step.action_config, [step.action_type === 'command' ? 'command' : 'url']: e.target.value } })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input text-sm font-mono text-primary focus:border-primary outline-none transition-colors"
              />
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">Timeout (seconds)</label>
              <input type="number" value={step.timeout_seconds || ''} placeholder="No timeout"
                onChange={(e) => onUpdate({ ...step, timeout_seconds: e.target.value ? parseInt(e.target.value) : null })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input text-sm text-primary focus:border-primary outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-xs font-medium text-secondary mb-1">On Failure</label>
              <select value={step.on_failure} onChange={(e) => onUpdate({ ...step, on_failure: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-border bg-input text-sm text-primary focus:border-primary outline-none transition-colors">
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
    tags: runbook?.tags?.join(', ') || '',
    is_active: runbook?.is_active ?? true,
    steps: runbook?.steps || []
  })

  const handleStepChange = (idx, field, value) => {
    const newSteps = [...form.steps]
    newSteps[idx] = { ...newSteps[idx], [field]: value }
    setForm({ ...form, steps: newSteps })
  }

  const addStep = (type) => {
    setForm({
      ...form,
      steps: [
        ...form.steps,
        {
          id: `step_${form.steps.length}_${new Date().getTime()}`,
          action_type: type,
          title: `New ${ACTION_TYPES.find(a => a.value === type)?.label}`,
          parameters: {},
          timeout_seconds: 300,
          on_failure: 'abort'
        }
      ]
    })
  }

  const moveStep = (idx, direction) => {
    if ((direction === -1 && idx === 0) || (direction === 1 && idx === form.steps.length - 1)) return
    const newSteps = [...form.steps]
    const temp = newSteps[idx]
    newSteps[idx] = newSteps[idx + direction]
    newSteps[idx + direction] = temp
    setForm({ ...form, steps: newSteps })
  }

  const removeStep = (idx) => {
    setForm({
      ...form,
      steps: form.steps.filter((_, i) => i !== idx)
    })
  }

  return (
    <div className="space-y-6">
      <div className="glass rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-heading mb-1">Name *</label>
            <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input focus:border-primary outline-none transition-colors text-primary" />
          </div>
          <div>
            <label className="block text-sm font-medium text-heading mb-1">Alert Type *</label>
            <input required value={form.alert_type} onChange={e => setForm({ ...form, alert_type: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input focus:border-primary outline-none transition-colors text-primary" />
          </div>
        </div>
        <div className="mb-4">
          <label className="block text-sm font-medium text-heading mb-1">Description</label>
          <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-border bg-input focus:border-primary outline-none transition-colors text-primary h-20" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-heading mb-1">Severity</label>
            <select value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input focus:border-primary outline-none transition-colors text-primary">
              <option value="">Any</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-heading mb-1">Tags</label>
            <input value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })}
              placeholder="comma separated"
              className="w-full px-3 py-2 rounded-lg border border-border bg-input focus:border-primary outline-none transition-colors text-primary" />
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-border">
          <label className="flex items-center gap-2 cursor-pointer w-fit">
            <input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} className="rounded text-primary focus:ring-primary" />
            <span className="text-sm font-medium text-heading">Active</span>
          </label>
        </div>
      </div>

      {/* Steps */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-heading">Steps ({form.steps.length})</h3>
          <div className="flex gap-2">
            {ACTION_TYPES.map(at => (
              <button key={at.value} type="button" onClick={() => addStep(at.value)}
                className="px-3 py-1.5 text-sm bg-elevated hover:bg-input border border-border rounded-lg text-primary transition-colors flex items-center gap-1">
                <Plus className="w-3 h-3" /> {at.icon} {at.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          {form.steps.map((step, idx) => (
            <StepEditor key={step.id} step={step} idx={idx} total={form.steps.length} onChange={handleStepChange} onMove={moveStep} onRemove={removeStep} />
          ))}
          {form.steps.length === 0 && (
            <div className="text-center py-8 text-muted border-2 border-dashed border-border rounded-xl">
              No steps defined. Add a step to get started.
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-3 justify-end pt-4 border-t border-border">
        <button onClick={onCancel} type="button"
          className="px-4 py-2 border border-border rounded-lg text-primary hover:bg-elevated transition-colors font-medium">
          Cancel
        </button>
        <button onClick={() => onSave(form)} type="button"
          className="px-4 py-2 rounded-lg font-medium transition-colors"
          style={{ background: 'rgba(99,102,241,0.9)', color: '#fff', border: 'none' }}>
          Save Runbook
        </button>
      </div>
    </div>
  )
}

function RunbookVersionsPanel({ runbook, onClose }) {
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchRunbookVersions(runbook.id)
      .then((data) => {
        if (!cancelled) setVersions(data.versions || [])
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load version history')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [runbook.id])

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/50" onClick={onClose} />
      {/* Panel */}
      <div className="w-full max-w-lg bg-[var(--color-bg,#0f1117)] border-l border-border flex flex-col h-full overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h2 className="text-lg font-semibold text-heading">Version History</h2>
            <p className="text-xs text-muted mt-0.5 truncate">{runbook.name}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-elevated transition-colors text-muted hover:text-primary">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && (
            <div className="flex justify-center py-10">
              <div className="w-6 h-6 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {error && <p className="text-red-400 text-sm text-center py-6">{error}</p>}
          {!loading && !error && versions.length === 0 && (
            <p className="text-muted text-sm text-center py-10">No version snapshots yet. Snapshots are created when a runbook is edited.</p>
          )}
          {versions.map((v) => (
            <div key={v.id} className="glass rounded-xl overflow-hidden">
              <button
                onClick={() => setExpanded(expanded === v.id ? null : v.id)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-elevated/40 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 text-xs font-semibold">v{v.version}</span>
                  <span className="text-sm text-secondary">{(v.steps || []).length} steps</span>
                </div>
                <div className="flex items-center gap-3">
                  {v.updated_at && (
                    <span className="text-xs text-muted">{new Date(v.updated_at).toLocaleString()}</span>
                  )}
                  {expanded === v.id ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
                </div>
              </button>
              {expanded === v.id && (
                <div className="px-4 pb-4 border-t border-border space-y-2 pt-3">
                  {(v.steps || []).length === 0 && (
                    <p className="text-muted text-xs">No steps in this snapshot.</p>
                  )}
                  {(v.steps || []).map((step, idx) => {
                    const at = ACTION_TYPES.find(a => a.value === step.action_type) || ACTION_TYPES[0]
                    return (
                      <div key={idx} className="flex items-center gap-2 text-sm">
                        <span className="text-muted font-mono text-xs w-5 shrink-0">{idx + 1}.</span>
                        <span className="text-base leading-none">{at.icon}</span>
                        <span className="text-secondary">{step.title || `Step ${idx + 1}`}</span>
                        <span className="text-xs text-muted ml-auto">{at.label}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function RunbooksPage() {
  const [runbooks, setRunbooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null) // null | 'new' | runbook object
  const [versionsRunbook, setVersionsRunbook] = useState(null)
  const [filterActive, setFilterActive] = useState(false)
  const { addToast } = useToasts()

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await fetchRunbooks(filterActive)
      setRunbooks(data.runbooks || [])
    } catch (err) {
      console.error(err)
      addToast('Failed to load runbooks', 'error')
    } finally {
      setLoading(false)
    }
  }, [filterActive, addToast])

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
      console.error(err)
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
      console.error(err)
      addToast('Failed to delete runbook', 'error')
    }
  }

  const handleDuplicate = async (id) => {
    try {
      await duplicateRunbook(id)
      addToast('Runbook duplicated', 'success')
      load()
    } catch (err) {
      console.error(err)
      addToast('Failed to duplicate runbook', 'error')
    }
  }

  if (editing) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-heading mb-6">
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
          <h1 className="text-2xl font-bold text-heading">Runbooks</h1>
          <p className="text-secondary text-sm mt-1">
            Visual runbook editor for structured incident response procedures
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm font-medium text-secondary">
            <input type="checkbox" checked={filterActive} onChange={(e) => setFilterActive(e.target.checked)} className="rounded" />
            Active only
          </label>
          <button onClick={() => setEditing('new')}
            className="flex items-center gap-2 px-4 py-2 font-semibold rounded-lg transition-colors"
            style={{ background: 'rgba(99,102,241,0.9)', color: '#fff', border: 'none' }}>
            <Plus className="w-4 h-4" /> New Runbook
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : runbooks.length === 0 ? (
        <div className="text-center py-16 text-muted">
          <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg text-heading">No runbooks yet</p>
          <p className="text-sm mt-1">Create your first runbook to automate incident response</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {runbooks.map(rb => (
            <div key={rb.id} className="glass rounded-xl p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-heading">{rb.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${rb.is_active ? 'bg-emerald-500/10 text-emerald-500' : 'bg-elevated text-muted'}`}>
                      {rb.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 text-xs font-semibold">
                      v{rb.version}
                    </span>
                  </div>
                  {rb.description && <p className="text-sm text-secondary mb-2">{rb.description}</p>}
                  <div className="flex items-center gap-4 text-xs text-muted">
                    <span>Alert: <strong>{rb.alert_type}</strong></span>
                    {rb.severity && <span>Severity: <strong>{rb.severity}</strong></span>}
                    <span>{(rb.steps || []).length} steps</span>
                    {rb.tags && rb.tags.length > 0 && (
                      <div className="flex gap-1">
                        {rb.tags.map(tag => (
                          <span key={tag} className="px-1.5 py-0.5 bg-elevated rounded text-xs">{tag}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setVersionsRunbook(rb)} className="p-2 rounded-lg hover:bg-elevated transition-colors text-muted hover:text-primary" title="Version history">
                    <History className="w-4 h-4" />
                  </button>
                  <button onClick={() => setEditing(rb)} className="p-2 rounded-lg hover:bg-elevated transition-colors text-muted hover:text-primary" title="Edit">
                    <Edit className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDuplicate(rb.id)} className="p-2 rounded-lg hover:bg-elevated transition-colors text-muted hover:text-primary" title="Duplicate">
                    <Copy className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(rb.id)} className="p-2 rounded-lg hover:bg-red-500/10 transition-colors text-red-500" title="Delete">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {/* Step preview */}
              {(rb.steps || []).length > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="flex items-center gap-2 overflow-x-auto pb-1">
                    {(rb.steps || []).map((step, idx) => {
                      const at = ACTION_TYPES.find(a => a.value === step.action_type) || ACTION_TYPES[0]
                      return (
                        <div key={idx} className="flex items-center gap-1">
                          {idx > 0 && <span className="text-muted">→</span>}
                          <span className="whitespace-nowrap px-2 py-1 rounded text-xs bg-elevated text-secondary font-medium">
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

      {versionsRunbook && (
        <RunbookVersionsPanel runbook={versionsRunbook} onClose={() => setVersionsRunbook(null)} />
      )}
    </div>
  )
}
