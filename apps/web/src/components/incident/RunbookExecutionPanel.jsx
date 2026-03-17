import { useState, useEffect, useCallback } from 'react'
import {
  getRunbookExecution,
  completeRunbookStep,
  skipRunbookStep,
  abandonRunbookExecution,
} from '../../services/api'

const STATUS_STYLES = {
  pending: 'bg-gray-700 text-gray-300',
  in_progress: 'bg-blue-900 text-blue-200',
  completed: 'bg-green-900 text-green-200',
  skipped: 'bg-yellow-900 text-yellow-200',
  failed: 'bg-red-900 text-red-200',
}

const EXEC_STATUS_STYLES = {
  in_progress: 'text-blue-400',
  completed: 'text-green-400',
  abandoned: 'text-gray-400',
}

function StepRow({ step, executionId, isActive, onUpdated }) {
  const [loading, setLoading] = useState(false)
  const [notes, setNotes] = useState('')
  const [showNotes, setShowNotes] = useState(false)

  const handleComplete = async () => {
    setLoading(true)
    try {
      const updated = await completeRunbookStep(executionId, step.step_order, notes || null)
      onUpdated(updated)
      setShowNotes(false)
      setNotes('')
    } catch (err) {
      console.error('Failed to complete step', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSkip = async () => {
    setLoading(true)
    try {
      const updated = await skipRunbookStep(executionId, step.step_order, notes || null)
      onUpdated(updated)
      setShowNotes(false)
      setNotes('')
    } catch (err) {
      console.error('Failed to skip step', err)
    } finally {
      setLoading(false)
    }
  }

  const canAct = isActive && step.status === 'pending'

  return (
    <div className="border border-gray-700 rounded-lg p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-gray-500 text-sm font-mono w-6 shrink-0">
            {step.step_order}
          </span>
          <div className="min-w-0">
            <p className="text-white font-medium truncate">
              {step.step_title || `Step ${step.step_order}`}
            </p>
            {step.step_action_type && (
              <p className="text-gray-500 text-xs">{step.step_action_type}</p>
            )}
          </div>
        </div>
        <span
          className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[step.status] || STATUS_STYLES.pending}`}
        >
          {step.status}
        </span>
      </div>

      {step.notes && (
        <p className="text-gray-400 text-sm pl-9">{step.notes}</p>
      )}
      {step.completed_at && (
        <p className="text-gray-600 text-xs pl-9">
          Completed {new Date(step.completed_at).toLocaleTimeString()}
        </p>
      )}

      {canAct && (
        <div className="pl-9 space-y-2">
          {showNotes ? (
            <div className="space-y-2">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes..."
                rows={2}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm resize-none focus:outline-none focus:border-indigo-500"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleComplete}
                  disabled={loading}
                  className="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-sm rounded font-medium disabled:opacity-50"
                >
                  {loading ? 'Saving...' : 'Complete'}
                </button>
                <button
                  onClick={handleSkip}
                  disabled={loading}
                  className="px-3 py-1.5 bg-yellow-700 hover:bg-yellow-600 text-white text-sm rounded font-medium disabled:opacity-50"
                >
                  {loading ? 'Saving...' : 'Skip'}
                </button>
                <button
                  onClick={() => setShowNotes(false)}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => setShowNotes(true)}
                className="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-sm rounded font-medium"
              >
                Complete
              </button>
              <button
                onClick={() => setShowNotes(true)}
                className="px-3 py-1.5 bg-yellow-700 hover:bg-yellow-600 text-white text-sm rounded font-medium"
              >
                Skip
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function RunbookExecutionPanel({ incidentId }) {
  const [execution, setExecution] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [abandoning, setAbandoning] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await getRunbookExecution(incidentId)
      setExecution(data)
      setError(null)
    } catch (err) {
      if (err?.response?.status === 404) {
        setExecution(null)
        setError(null)
      } else {
        setError('Failed to load runbook execution')
      }
    } finally {
      setLoading(false)
    }
  }, [incidentId])

  useEffect(() => {
    load()
  }, [load])

  const handleUpdated = (updated) => {
    setExecution(updated)
  }

  const handleAbandon = async () => {
    if (!execution) return
    setAbandoning(true)
    try {
      const updated = await abandonRunbookExecution(execution.id)
      setExecution(updated)
    } catch (err) {
      console.error('Failed to abandon execution', err)
    } finally {
      setAbandoning(false)
    }
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-4 bg-gray-700 rounded w-40" />
        <div className="h-16 bg-gray-800 rounded" />
        <div className="h-16 bg-gray-800 rounded" />
      </div>
    )
  }

  if (error) {
    return <p className="text-red-400 text-sm">{error}</p>
  }

  if (!execution) {
    return (
      <p className="text-gray-500 text-sm">No runbook execution for this incident yet.</p>
    )
  }

  const completedCount = execution.steps.filter((s) =>
    ['completed', 'skipped'].includes(s.status)
  ).length
  const total = execution.steps.length
  const progress = total > 0 ? Math.round((completedCount / total) * 100) : 0
  const isActive = execution.status === 'in_progress'

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span
            className={`text-sm font-medium ${EXEC_STATUS_STYLES[execution.status] || 'text-gray-400'}`}
          >
            {execution.status === 'in_progress'
              ? 'In Progress'
              : execution.status === 'completed'
              ? 'Completed'
              : 'Abandoned'}
          </span>
          <span className="text-gray-500 text-xs ml-2">
            v{execution.runbook_version} · {completedCount}/{total} steps
          </span>
        </div>
        {isActive && (
          <button
            onClick={handleAbandon}
            disabled={abandoning}
            className="px-3 py-1.5 bg-gray-700 hover:bg-red-800 text-gray-300 hover:text-white text-xs rounded transition-colors disabled:opacity-50"
          >
            {abandoning ? 'Abandoning...' : 'Abandon'}
          </button>
        )}
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="w-full bg-gray-700 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all ${
              execution.status === 'completed' ? 'bg-green-500' : 'bg-indigo-500'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Steps */}
      <div className="space-y-2">
        {execution.steps.map((step) => (
          <StepRow
            key={step.id}
            step={step}
            executionId={execution.id}
            isActive={isActive}
            onUpdated={handleUpdated}
          />
        ))}
      </div>

      {execution.completed_at && (
        <p className="text-gray-600 text-xs">
          Finished {new Date(execution.completed_at).toLocaleString()}
        </p>
      )}
    </div>
  )
}
