import { Link } from 'react-router-dom'
import { Home, ArrowLeft, Search, AlertTriangle } from 'lucide-react'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="text-center max-w-md px-6">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full mb-6" style={{ background: 'var(--glow-indigo)' }}>
          <AlertTriangle size={40} style={{ color: 'var(--neon-indigo)' }} />
        </div>
        
        <h1 className="text-4xl font-bold mb-3" style={{ color: 'var(--text-heading)' }}>
          404
        </h1>
        <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-heading)' }}>
          Page Not Found
        </h2>
        <p className="text-muted mb-8" style={{ fontSize: 14 }}>
          The page you're looking for doesn't exist or has been moved.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{ 
              background: 'var(--gradient-primary)', 
              color: '#fff',
              fontSize: 14,
              fontWeight: 600
            }}
          >
            <Home size={16} />
            Go to Dashboard
          </Link>
          <Link
            to="/alerts"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{ 
              background: 'var(--bg-input)', 
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 14,
              fontWeight: 600
            }}
          >
            <Search size={16} />
            View Alerts
          </Link>
          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg transition-all"
            style={{ 
              background: 'var(--bg-input)', 
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              fontSize: 14,
              fontWeight: 600
            }}
          >
            <ArrowLeft size={16} />
            Go Back
          </button>
        </div>

        <div className="mt-12 pt-8 border-t" style={{ borderColor: 'var(--border)' }}>
          <p className="text-xs text-muted mb-4">Quick Links:</p>
          <div className="flex flex-wrap gap-2 justify-center">
            <Link to="/dashboard" className="text-xs text-muted hover:text-primary transition-colors">Dashboard</Link>
            <span className="text-xs text-muted">•</span>
            <Link to="/alerts" className="text-xs text-muted hover:text-primary transition-colors">Alerts</Link>
            <span className="text-xs text-muted">•</span>
            <Link to="/live" className="text-xs text-muted hover:text-primary transition-colors">Live Feed</Link>
            <span className="text-xs text-muted">•</span>
            <Link to="/settings" className="text-xs text-muted hover:text-primary transition-colors">Settings</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
