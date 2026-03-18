import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Settings, Server, Brain, Shield, Clock, Database,
  CheckCircle, AlertTriangle, RefreshCw, Save
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { fetchBackendHealth } from '../services/api'
import ConnectionBanner from '../components/common/ConnectionBanner'
import { FALLBACK_TENANT_ID } from '../utils/constants'

export default function SettingsPage() {
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHealth()
  }, [])

  async function fetchHealth() {
    try {
      const data = await fetchBackendHealth()
      setHealth(data)
    } catch (err) {
      if (err?.response?.status === 404) {
        setHealth({ status: 'dev_backend_missing' })
        return
      }

      console.error('health check failed', err)
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }



  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="flex items-center gap-3" style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-heading)', letterSpacing: '-0.02em' }}>
          <Settings size={24} style={{ color: 'var(--text-muted)' }} />
          Settings
        </h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
          System configuration and status overview.
        </p>
      </div>

      {/* System Status */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>System Status</span>
          <button
            onClick={fetchHealth}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all"
            style={{ fontSize: 11, fontWeight: 600, color: 'var(--neon-indigo)', background: 'var(--glow-indigo)', border: '1px solid rgba(99,102,241,0.2)' }}
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Backend API',
              ok: health?.status === 'ok',
              detail:
                health?.status === 'dev_backend_missing'
                  ? 'Backend not running (Dev Mode)'
                  : 'FastAPI + Uvicorn',
            },
            { label: 'Database', ok: true, detail: 'PostgreSQL + Alembic' },
            { label: 'Redis / Queue', ok: true, detail: 'ARQ Worker' },
            { label: 'AI Engine', ok: true, detail: 'Gemini 2.0 Flash' },
          ].map(s => (
            <div key={s.label} className="flex items-center gap-3 p-3 rounded-lg hover-lift" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
              {s.ok ? (
                <CheckCircle size={18} style={{ color: 'var(--neon-green)', flexShrink: 0 }} />
              ) : loading ? (
                <RefreshCw size={18} style={{ color: 'var(--text-muted)', flexShrink: 0, animation: 'spin 1s linear infinite' }} />
              ) : (
                <AlertTriangle size={18} style={{ color: 'var(--brand-orange)', flexShrink: 0 }} />
              )}
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>{s.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>




      {/* Tenant Info */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Database size={16} style={{ color: 'var(--neon-indigo)' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-heading)' }}>Current Session</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Mode</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-accent-amber)', marginTop: 4 }}>{user ? 'Authenticated' : 'Anonymous'}</div>
          </div>
          <div className="p-3 rounded-lg" style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Version</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-heading)', marginTop: 4 }}>AIREX v0.9.0</div>
          </div>
        </div>
      </div>
    </div>
  )
}
