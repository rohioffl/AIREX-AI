import { useState, useEffect, useCallback } from 'react'
import { Key, Activity, Plus, Trash2, RefreshCw, Copy, Check } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import {
  fetchOrganizations,
  fetchApiKeys,
  createApiKey,
  revokeApiKey,
  fetchAuditEvents,
} from '../services/api'
import { extractErrorMessage } from '../utils/errorHandler'

const TABS = [
  { id: 'api-keys', label: 'API Keys', icon: Key },
  { id: 'audit', label: 'Audit Log', icon: Activity },
]

export default function OrgSettingsPage() {
  useAuth()
  const [activeTab, setActiveTab] = useState('api-keys')
  const [org, setOrg] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadOrg()
  }, [])

  async function loadOrg() {
    try {
      setLoading(true)
      const orgs = await fetchOrganizations()
      if (orgs.length > 0) setOrg(orgs[0])
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin" size={24} style={{ color: 'var(--neon-cyan)' }} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="glass-red rounded-lg p-4">
          <p style={{ color: 'var(--neon-red)' }}>{error}</p>
        </div>
      </div>
    )
  }

  if (!org) {
    return (
      <div className="p-8">
        <p style={{ color: 'var(--text-secondary)' }}>No organization found.</p>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Organization Settings
        </h1>
        <p style={{ color: 'var(--text-secondary)' }} className="mt-1">
          {org.name} &middot; <span className="font-mono text-sm">{org.slug}</span>
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b" style={{ borderColor: 'var(--border-color)' }}>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === id
                ? 'border-cyan-400'
                : 'border-transparent hover:border-gray-500'
            }`}
            style={{
              color: activeTab === id ? 'var(--neon-cyan)' : 'var(--text-secondary)',
            }}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'api-keys' && <ApiKeysTab orgId={org.id} />}
      {activeTab === 'audit' && <AuditTab orgId={org.id} />}
    </div>
  )
}

// ─── API Keys Tab ────────────────────────────────────────────────────────────

function ApiKeysTab({ orgId }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [newKey, setNewKey] = useState(null)
  const [form, setForm] = useState({ name: '', expires_in_days: '' })
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setKeys(await fetchApiKeys(orgId))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [orgId])

  useEffect(() => { load() }, [load])

  async function handleCreate(e) {
    e.preventDefault()
    if (!form.name.trim()) return
    setCreating(true)
    setError(null)
    try {
      const result = await createApiKey(orgId, {
        name: form.name.trim(),
        expires_in_days: form.expires_in_days ? parseInt(form.expires_in_days) : null,
      })
      setNewKey(result)
      setShowForm(false)
      setForm({ name: '', expires_in_days: '' })
      await load()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke(keyId) {
    if (!confirm('Revoke this API key? This cannot be undone.')) return
    try {
      await revokeApiKey(orgId, keyId)
      await load()
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function copyKey() {
    await navigator.clipboard.writeText(newKey.key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div>
      {error && (
        <div className="mb-4 glass-red rounded-lg p-3">
          <p className="text-sm" style={{ color: 'var(--neon-red)' }}>{error}</p>
        </div>
      )}

      {newKey && (
        <div className="mb-6 glass-green rounded-lg p-4">
          <p className="text-sm font-semibold mb-2" style={{ color: 'var(--neon-green)' }}>
            API key created — copy it now. It will not be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono p-2 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', wordBreak: 'break-all' }}>
              {newKey.key}
            </code>
            <button onClick={copyKey} className="p-2 rounded glass-button" title="Copy">
              {copied ? <Check size={16} style={{ color: 'var(--neon-green)' }} /> : <Copy size={16} />}
            </button>
          </div>
          <button
            onClick={() => setNewKey(null)}
            className="mt-2 text-xs"
            style={{ color: 'var(--text-secondary)' }}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>API Keys</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="glass-button flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
          style={{ color: 'var(--neon-cyan)' }}
        >
          <Plus size={15} /> New Key
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 glass rounded-lg p-4">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Key name (e.g. CI Pipeline)"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="flex-1 glass-input rounded px-3 py-2 text-sm"
              style={{ color: 'var(--text-primary)' }}
            />
            <input
              type="number"
              placeholder="Expires in days (optional)"
              value={form.expires_in_days}
              onChange={e => setForm(f => ({ ...f, expires_in_days: e.target.value }))}
              className="w-48 glass-input rounded px-3 py-2 text-sm"
              style={{ color: 'var(--text-primary)' }}
              min={1}
            />
            <button
              type="submit"
              disabled={creating}
              className="glass-button px-4 py-2 rounded text-sm font-medium"
              style={{ color: 'var(--neon-cyan)' }}
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="glass-button px-3 py-2 rounded text-sm"
              style={{ color: 'var(--text-secondary)' }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="flex justify-center p-8">
          <RefreshCw className="animate-spin" size={20} style={{ color: 'var(--neon-cyan)' }} />
        </div>
      ) : keys.length === 0 ? (
        <p className="text-sm text-center py-8" style={{ color: 'var(--text-secondary)' }}>
          No API keys yet.
        </p>
      ) : (
        <div className="space-y-2">
          {keys.map(key => (
            <div key={key.id} className="glass rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{key.name}</p>
                <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  {key.key_prefix}…
                  {key.expires_at && (
                    <span className="ml-3">Expires {new Date(key.expires_at).toLocaleDateString()}</span>
                  )}
                </p>
              </div>
              <button
                onClick={() => handleRevoke(key.id)}
                className="glass-button p-2 rounded"
                title="Revoke"
              >
                <Trash2 size={15} style={{ color: 'var(--neon-red)' }} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Audit Log Tab ────────────────────────────────────────────────────────────

function AuditTab({ orgId }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionFilter, setActionFilter] = useState('')

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const params = {}
      if (actionFilter) params.action = actionFilter
      setEvents(await fetchAuditEvents(orgId, params))
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [orgId, actionFilter])

  useEffect(() => { load() }, [load])

  const actionColors = {
    'org_member.added': 'var(--neon-green)',
    'org_member.removed': 'var(--neon-red)',
    'org_member.role_changed': 'var(--neon-yellow)',
    'org_member.role_updated': 'var(--neon-yellow)',
    'api_key.created': 'var(--neon-cyan)',
    'api_key.revoked': 'var(--neon-orange)',
  }

  return (
    <div>
      {error && (
        <div className="mb-4 glass-red rounded-lg p-3">
          <p className="text-sm" style={{ color: 'var(--neon-red)' }}>{error}</p>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Audit Log</h2>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Filter by action…"
            value={actionFilter}
            onChange={e => setActionFilter(e.target.value)}
            className="glass-input rounded px-3 py-1.5 text-sm w-52"
            style={{ color: 'var(--text-primary)' }}
          />
          <button onClick={load} className="glass-button p-2 rounded" title="Refresh">
            <RefreshCw size={15} style={{ color: 'var(--neon-cyan)' }} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-8">
          <RefreshCw className="animate-spin" size={20} style={{ color: 'var(--neon-cyan)' }} />
        </div>
      ) : events.length === 0 ? (
        <p className="text-sm text-center py-8" style={{ color: 'var(--text-secondary)' }}>
          No audit events found.
        </p>
      ) : (
        <div className="space-y-1">
          {events.map(ev => (
            <div key={ev.id} className="glass rounded-lg p-3 flex items-start gap-3">
              <span
                className="text-xs font-mono font-semibold px-2 py-0.5 rounded shrink-0"
                style={{
                  color: actionColors[ev.action] || 'var(--neon-purple)',
                  background: 'var(--bg-tertiary)',
                }}
              >
                {ev.action}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {ev.actor_email || ev.actor_id || 'system'}
                  {ev.entity_type && (
                    <span> &middot; {ev.entity_type} {ev.entity_id && <span className="font-mono">{ev.entity_id.slice(0, 8)}</span>}</span>
                  )}
                </p>
              </div>
              <span className="text-xs shrink-0" style={{ color: 'var(--text-tertiary)' }}>
                {new Date(ev.created_at).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
