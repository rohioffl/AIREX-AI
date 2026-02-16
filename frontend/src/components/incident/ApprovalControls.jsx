import { useState } from 'react'
import { ShieldCheck, ShieldX, Loader } from 'lucide-react'
import { approveIncident } from '../../services/api'
import ConfirmationModal from '../common/ConfirmationModal'

export default function ApprovalControls({ incident }) {
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [error, setError] = useState(null)

  if (incident.state !== 'AWAITING_APPROVAL') return null

  const actionType = incident.recommendation?.proposed_action
  if (!actionType) return null

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

  return (
    <div className="glass rounded-xl p-5" style={{ borderLeft: '4px solid #f59e0b', background: 'rgba(245,158,11,0.03)' }}>
      <div className="flex items-center gap-2 mb-3">
        <div className="h-5 w-5 rounded-full flex items-center justify-center" style={{ background: 'rgba(245,158,11,0.15)' }}>
          <ShieldCheck size={12} style={{ color: '#fbbf24' }} />
        </div>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Approval Required
        </h3>
      </div>

      <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
        Ready to execute{' '}
        <span className="px-1.5 py-0.5 rounded" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#818cf8', background: 'rgba(99,102,241,0.1)' }}>{actionType}</span>
      </p>

      {error && (
        <p className="mt-2 px-3 py-2 rounded-md" style={{ fontSize: 12, color: '#fb7185', background: 'rgba(244,63,94,0.1)' }}>{error}</p>
      )}

      <div className="mt-5 flex gap-3">
        <button
          onClick={() => setModalOpen(true)}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 12px rgba(99,102,241,0.2)' }}
        >
          {loading ? <><Loader size={14} className="animate-spin" /> Executing...</> : <><ShieldCheck size={14} /> Approve & Execute</>}
        </button>
        <button
          disabled={loading}
          className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all disabled:opacity-50"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
        >
          <ShieldX size={14} /> Escalate
        </button>
      </div>

      <ConfirmationModal
        open={modalOpen}
        title="Confirm Execution"
        message={`You are about to execute "${actionType}" on this incident. This action will be logged and cannot be undone.`}
        onConfirm={handleApprove}
        onCancel={() => setModalOpen(false)}
      />
    </div>
  )
}
