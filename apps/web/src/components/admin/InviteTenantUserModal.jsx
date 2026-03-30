import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Mail, X } from 'lucide-react'

import { useToasts } from '../../context/ToastContext'
import { inviteTenantUser } from '../../services/api'
import { extractErrorMessage } from '../../utils/errorHandler'

const inputCls = {
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13,
  outline: 'none',
  width: '100%',
}

const ROLE_OPTIONS = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'operator', label: 'Operator' },
  { value: 'admin', label: 'Admin' },
]

export default function InviteTenantUserModal({ tenant, onClose, onInvited }) {
  const { addToast } = useToasts()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('viewer')
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email.trim()) return
    setSaving(true)
    try {
      const data = await inviteTenantUser(tenant.id, {
        email: email.trim(),
        display_name: displayName.trim(),
        role,
      })
      setResult(data)
      if (onInvited) onInvited(data)
      addToast({ title: 'Invitation sent', message: `Invite email sent to ${data.email}`, severity: 'LOW' })
    } catch (err) {
      addToast({ title: 'Error', message: extractErrorMessage(err) || 'Failed to invite user', severity: 'CRITICAL' })
    } finally {
      setSaving(false)
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(2px)' }}
    >
      <div
        className="glass rounded-2xl p-6 w-full max-w-md space-y-5 relative"
        style={{ border: '1px solid var(--border)', boxShadow: '0 20px 60px rgba(0,0,0,0.4)' }}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-2">
          <Mail size={18} style={{ color: 'var(--brand-orange)' }} />
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
            Invite User to {tenant?.display_name || tenant?.name || 'Tenant'}
          </h3>
        </div>

        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
          The invited user will only have access to this tenant. No organisation membership will be created.
        </p>

        {!result ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Email address <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                style={inputCls}
              />
            </div>

            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Display name <span style={{ color: 'var(--text-muted)' }}>(optional)</span>
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Jane Doe"
                maxLength={200}
                style={inputCls}
              />
            </div>

            <div>
              <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)} style={inputCls} aria-label="Invited user role">
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>

            <div className="flex gap-3 justify-end pt-1">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--bg-input)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || !email.trim()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ background: 'var(--gradient-primary)', color: '#fff' }}
              >
                <Mail size={14} />
                {saving ? 'Sending…' : 'Send Invite'}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="rounded-xl p-4 space-y-2" style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.24)' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#22c55e' }}>Invitation sent</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                An invitation email has been sent to <strong style={{ color: 'var(--text-primary)' }}>{result.email}</strong>. It expires in 7 days.
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{ background: 'var(--gradient-primary)', color: '#fff' }}
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}
