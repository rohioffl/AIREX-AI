import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Ban, Loader } from 'lucide-react'
import { approveIncident, rejectIncident } from '../../services/api'
import ConfirmationModal from '../common/ConfirmationModal'

export default function ApprovalControls({ incident }) {
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [error, setError] = useState(null)
  const [rejectNote, setRejectNote] = useState(incident.meta?._manual_review_reason || '')
  const navigate = useNavigate()

  const manualRequired = Boolean(incident.meta?._manual_review_required)
  const recommendation = incident.recommendation || incident.meta?.recommendation
  const actionType = recommendation?.proposed_action
  const canApprove = incident.state === 'AWAITING_APPROVAL' && Boolean(actionType)

  if (!manualRequired && !canApprove) return null

  const idempotencyKey = `${incident.id}:${actionType}`

  async function handleApprove() {
    setModalOpen(false)
    setLoading(true)
    setError(null)
    try {
      await approveIncident(incident.id, actionType, idempotencyKey)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setLoading(false)
    }
  }

  const trimmedNote = rejectNote.trim()
  const canReject = trimmedNote.length >= 3 && trimmedNote.length <= 500

  function openRejectModal() {
    if (!canReject) return
    setRejectModalOpen(true)
  }

  async function handleRejectConfirm() {
    setLoading(true)
    setError(null)
    try {
      await rejectIncident(incident.id, trimmedNote)
      navigate('/rejected', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setLoading(false)
      return
    }
    setLoading(false)
    setRejectNote('')
  }

  return (
    <div className="glass rounded-xl p-5" style={{ borderLeft: manualRequired ? '4px solid #f87171' : '4px solid #22d3ee', background: manualRequired ? 'rgba(248,113,113,0.06)' : 'rgba(34,211,238,0.06)' }}>
      <div className="flex items-center gap-2 mb-3">
        <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: manualRequired ? 'rgba(248,113,113,0.15)' : 'rgba(34,211,238,0.15)' }}>
          <ShieldCheck size={12} style={{ color: manualRequired ? '#f87171' : '#22d3ee' }} />
        </div>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: manualRequired ? '#f87171' : '#22d3ee', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {manualRequired ? 'Manual Review' : 'Approval Required'}
        </h3>
      </div>

      {canApprove ? (
        <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          Ready to execute{' '}
          <span className="px-1.5 py-0.5 rounded" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#818cf8', background: 'rgba(99,102,241,0.1)' }}>{actionType}</span>
          {recommendation?.risk_level && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
              Risk: {recommendation.risk_level}
            </span>
          )}
        </p>
      ) : (
        <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          Automation requested operator input. Add a note explaining the resolution and reject to archive the alert.
        </p>
      )}

      <div className="mt-4">
        <label htmlFor="reject-note" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          Add a rejection note
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{trimmedNote.length}/500</span>
        </label>
        <textarea
          id="reject-note"
          value={rejectNote}
          onChange={(e) => setRejectNote(e.target.value.slice(0, 500))}
          placeholder="Explain why this runbook should not execute..."
          rows={3}
          style={{
            width: '100%',
            marginTop: 6,
            padding: '10px 12px',
            borderRadius: 12,
            border: '1px solid var(--border)',
            background: 'var(--bg-input)',
            color: 'var(--text-primary)',
            fontSize: 13,
            resize: 'vertical',
          }}
          disabled={loading}
        />
        <p style={{ fontSize: 11, color: trimmedNote.length < 3 ? '#f97316' : 'var(--text-muted)', marginTop: 4 }}>
          {trimmedNote.length < 3 ? 'Provide at least 3 characters' : 'This note will appear in the manual-review log'}
        </p>
      </div>

      {error && (
        <p className="mt-2 px-3 py-2 rounded-md" style={{ fontSize: 12, color: '#fb7185', background: 'rgba(244,63,94,0.1)' }}>{error}</p>
      )}

      <div className="mt-5 flex gap-3 flex-wrap">
        {canApprove && (
          <button
            onClick={() => setModalOpen(true)}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 12px rgba(99,102,241,0.2)' }}
          >
            {loading ? <><Loader size={14} className="animate-spin" /> Processing...</> : <><ShieldCheck size={14} /> Approve & Execute</>}
          </button>
        )}
        <button
          onClick={openRejectModal}
          disabled={loading || !canReject}
          className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all disabled:opacity-50"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
        >
          <Ban size={14} /> Reject (Skip)
        </button>
      </div>

      <ConfirmationModal
        open={modalOpen}
        title="Confirm Execution"
        message={`You are about to execute "${actionType}" on this incident. This action will be logged and cannot be undone.`}
        onConfirm={handleApprove}
        onCancel={() => setModalOpen(false)}
      />

      <ConfirmationModal
        open={rejectModalOpen}
        title="Reject Incident"
        message={
          <div className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            <p>This incident will move to the Rejected queue.</p>
            <div className="px-3 py-2 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              {trimmedNote || 'No note provided'}
            </div>
            <p>This action can be reversed only by reopening the alert manually.</p>
          </div>
        }
        confirmLabel="Reject"
        confirmTone="danger"
        loading={loading}
        onConfirm={() => {
          setRejectModalOpen(false)
          handleRejectConfirm()
        }}
        onCancel={() => setRejectModalOpen(false)}
      />
    </div>
  )
}
